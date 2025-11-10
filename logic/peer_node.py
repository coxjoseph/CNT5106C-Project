import asyncio
import errno
from typing import Dict, Optional, Iterable
from .bitfield import Bitfield
from .piece_store import PieceStore
from .request_manager import RequestManager
from .choking_manager import ChokingManager
from .peer_logic import PeerLogic
from net.protocol_logger import TextEventLogger
import erro
import logging

logger = logging.getLogger(__name__)


class NeighborState:
    def __init__(self, peer_id: int, logic: PeerLogic):
        self.peer_id = peer_id
        self.logic = logic
        self.we_choke_them: bool = True


class PeerNode:
    """
    Controls local state and policy:
      - local bitfield & PieceStore
      - registry of neighbors
      - request scheduling
      - choke/unchoke selection
    """

    def __init__(self, total_pieces: int, piece_size: int, last_piece_size: int,
                 data_dir: str, start_with_full_file: bool,
                 k_preferred: int, preferred_interval_sec: int, optimistic_interval_sec: int, self_id: int,
                 all_peer_ids: set[int],
                 file_name: str):
        self.total_pieces = total_pieces
        self.store = PieceStore(total_pieces, piece_size, last_piece_size, data_dir, start_full=start_with_full_file)
        self.local_bits: Bitfield = self.store.bitfield()

        self.requests = RequestManager(total_pieces)
        self.choking = ChokingManager(k_preferred)
        self.preferred_interval = preferred_interval_sec
        self.optimistic_interval = optimistic_interval_sec
        self.logger = TextEventLogger(self_id=self_id)
        self.self_id = self_id
        self._registry: Dict[int, NeighborState] = {}

        self.all_peers = all_peer_ids
        self.file_name = file_name

        self._complete_peers = set()
        if self.local_bits.count() == self.total_pieces:
            self._complete_peers.add(self_id)
        self._all_done = asyncio.Event()
        self._check_global_completion()

    async def wait_until_all_complete(self):
        await self._all_done.wait()

    def mark_peer_complete(self, peer_id: int) -> None:
        self._complete_peers.add(peer_id)
        self._check_global_completion()

    def _check_global_completion(self):
        if self._complete_peers == self.all_peers:
            self._all_done.set()

    # ------- factory for the networking Connector -------
    def make_callbacks(self) -> PeerLogic:
        return PeerLogic(self)

    # ------- registry & helpers -------
    def register_neighbor(self, logic: PeerLogic) -> None:
        assert logic.peer_id is not None
        self._registry[logic.peer_id] = NeighborState(logic.peer_id, logic)
        # Send our bitfield (only once) if we haven't yet and have pieces.

        if logic.their_bits.count() == self.total_pieces:
            self._complete_peers.add(logic.peer_id)
            self._check_global_completion()

        if not logic.sent_bitfield and self.local_bits.count() > 0 and logic.wire:
            logic.wire.send_bitfield(self.local_bits.to_bytes())
            logic._sent_bitfield = True
        # Immediately compute interest toward them
        self.recompute_interest(logic)

    def on_disconnect(self, logic: PeerLogic) -> None:
        if logic.peer_id is None:
            return
        # clear any inflight piece assigned to this neighbor
        self.requests.clear_inflight_for_peer(logic.peer_id)
        self._registry.pop(logic.peer_id, None)

    def we_choke_them(self, peer_id: int) -> bool:
        ns = self._registry.get(peer_id)
        return True if ns is None else ns.we_choke_them

    def neighbors(self) -> Iterable[NeighborState]:
        return list(self._registry.values())

    # ------- interest / request -------
    def recompute_interest(self, logic: PeerLogic) -> None:
        """Send interested/not interested based on whether neighbor has something we need."""
        if logic.wire is None or logic.peer_id is None:
            return
        missing = self.local_bits.missing_from(logic.their_bits)
        want = bool(missing)
        # Track our interest flag on the logic side using the wire (no need to store duplicate)
        # Idempotence: Networking tolerates duplicate sends, but we can be conservative if you track a flag.
        if want:
            logic.wire.send_interested()
        else:
            logic.wire.send_not_interested()

    def maybe_request_next(self, logic: PeerLogic) -> None:
        if logic.wire is None or logic.peer_id is None:
            return
        if logic.they_choke_us:
            return
        idx = self.requests.choose_for_neighbor(logic.peer_id, logic.their_bits, self.local_bits)
        if idx is not None:
            # Enforce correct size at PieceStore layer; the sender should send the right size
            logic.wire.send_request(idx)
            self.requests.mark_inflight(logic.peer_id, idx)

    def handle_piece(self, logic: PeerLogic, index: int, data: bytes) -> None:
        if not self.store.write_piece(index, data):
            return
        self.requests.complete(index)
        self.local_bits.set(index, True)

        have_cnt = self.local_bits.count()
        if logic.peer_id is not None:
            self.logger.downloaded_piece_from(logic.peer_id, index, have_cnt)

        for ns in self.neighbors():
            if ns.logic.wire:
                ns.logic.wire.send_have(index)

        # recompute interest, request again
        for ns in self.neighbors():
            self.recompute_interest(ns.logic)
        self.maybe_request_next(logic)

        if have_cnt == self.total_pieces:
            self.logger.downloaded_complete_file()
            self._complete_peers.add(self.self_id)
            try:
                self.store.reconstruct_full_file(self.file_name)
            except FileExistsError:
                logger.info(f'File {self.file_name} already exists - skipping')

            except OSError as e:
                if e.errno in (errno.EEXIST, errno.ENOTDIR):
                    logger.warning(f'Failed to reconstruct {self.file_name}: {e}')
            else:
                raise

            self._check_global_completion()

    # ------- choking timers -------
    async def run_choking_loops(self):
        async def preferred_loop():
            while True:
                await asyncio.sleep(self.preferred_interval)
                interested = [ns.peer_id for ns in self.neighbors() if ns.logic.they_interested_in_us]
                selected = self.choking.select_preferred(interested, self.local_bits.count() == self.total_pieces)
                self.logger.preferred_neighbors(selected)
                selected_set = set(selected)

                for ns in self.neighbors():
                    if ns.logic.wire is None:
                        continue
                    if ns.peer_id in selected_set and ns.we_choke_them:
                        ns.logic.wire.send_unchoke()
                        ns.we_choke_them = False
                    elif ns.peer_id not in selected_set and not ns.we_choke_them:
                        ns.logic.wire.send_choke()
                        ns.we_choke_them = True

        async def optimistic_loop():
            while True:
                await asyncio.sleep(self.optimistic_interval)
                choked_interested = [ns.peer_id for ns in self.neighbors()
                                     if ns.logic.they_interested_in_us and ns.we_choke_them]
                pick = self.choking.pick_optimistic(choked_interested)
                if pick is None:
                    continue
                self.logger.optimistic_pick(pick)
                ns = self._registry.get(pick)
                if ns and ns.logic.wire and ns.we_choke_them:
                    ns.logic.wire.send_unchoke()
                    ns.we_choke_them = False

        await asyncio.gather(preferred_loop(), optimistic_loop())

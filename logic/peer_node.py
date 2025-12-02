import asyncio
import errno
from typing import Optional, Iterable
from .bitfield import Bitfield
from .piece_store import PieceStore
from .request_manager import RequestManager
from .choking_manager import ChokingManager
from .peer_logic import PeerLogic
import errno
import logging

logger = logging.getLogger(__name__)


class NeighborState:
    def __init__(self, peer_id: int, logic: PeerLogic):
        self.peer_id = peer_id
        self.logic = logic
        self.we_choke_them: bool = True


class PeerNode:

    def __init__(self, total_pieces: int, piece_size: int, last_piece_size: int, data_dir: str,
                 start_with_full_file: bool, k_preferred: int, preferred_interval_sec: int,
                 optimistic_interval_sec: int, self_id: int, all_peer_ids: set[int], file_name: str):

        logger.info(f"starts process with k={k_preferred}, p={preferred_interval_sec}, m={optimistic_interval_sec}")

        self.total_pieces = total_pieces
        self.store = PieceStore(total_pieces, piece_size, last_piece_size, data_dir, start_full=start_with_full_file)
        self.local_bits: Bitfield = self.store.bitfield()

        logger.info(f"has bitfield {self.local_bits}")

        self.requests = RequestManager(total_pieces)
        self.choking = ChokingManager(k_preferred)
        self.preferred_interval = preferred_interval_sec
        self.optimistic_interval = optimistic_interval_sec
        self.self_id = self_id
        self._registry: dict[int, NeighborState] = {}

        self.all_peers = all_peer_ids
        self.file_name = file_name

        self._complete_peers = set()
        if self.local_bits.count() == self.total_pieces:
            self._complete_peers.add(self_id)
        self._all_done = asyncio.Event()
        self._check_global_completion()

    async def wait_until_all_complete(self) -> None:
        await self._all_done.wait()
        logger.info("is closing...")

    def mark_peer_complete(self, peer_id: int) -> None:
        self._complete_peers.add(peer_id)
        self._check_global_completion()

    def _check_global_completion(self) -> None:
        if self._complete_peers == self.all_peers:
            self._all_done.set()
            logger.info("believes all peers are complete.")

    def make_callbacks(self) -> PeerLogic:
        return PeerLogic(self)

    def register_neighbor(self, logic: PeerLogic) -> None:
        assert logic.peer_id is not None
        self._registry[logic.peer_id] = NeighborState(logic.peer_id, logic)

        if logic.their_bits.count() == self.total_pieces:
            self._complete_peers.add(logic.peer_id)
            self._check_global_completion()

        if not logic.sent_bitfield and self.local_bits.count() > 0 and logic.wire:
            logic.wire.send_bitfield(self.local_bits.to_bytes())
            logic._sent_bitfield = True

    def on_disconnect(self, logic: PeerLogic) -> None:
        if logic.peer_id is None:
            return

        self.requests.clear_inflight_for_peer(logic.peer_id)
        self._registry.pop(logic.peer_id, None)

    def we_choke_them(self, peer_id: int) -> bool:
        ns = self._registry.get(peer_id)
        return True if ns is None else ns.we_choke_them

    def neighbors(self) -> Iterable[NeighborState]:
        return list(self._registry.values())

    def recompute_interest(self, logic: PeerLogic) -> None:
        if logic.wire is None or logic.peer_id is None:
            return
        missing = self.local_bits.missing_from(logic.their_bits)
        want = bool(missing)
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
            logic.wire.send_request(idx)
            self.requests.mark_inflight(logic.peer_id, idx)

    def handle_piece(self, logic: PeerLogic, index: int, data: bytes) -> None:
        if not self.store.write_piece(index, data):
            return
        self.requests.complete(index)
        self.local_bits.set(index, True)

        have_cnt = self.local_bits.count()
        if logic.peer_id is not None:
            logger.info(f"has downloaded the piece [{index}] from Peer [{logic.peer_id}]. "
                        f"Now the number of pieces it has is [{have_cnt}].")

        for ns in self.neighbors():
            if ns.logic.wire:
                ns.logic.wire.send_have(index)

        for ns in self.neighbors():
            self.recompute_interest(ns.logic)
        self.maybe_request_next(logic)

        if have_cnt == self.total_pieces:
            logger.info(f'has downloaded the complete file')
            self._complete_peers.add(self.self_id)
            try:
                self.store.reconstruct_full_file(self.file_name)
            except FileExistsError:
                logger.info(f'File {self.file_name} already exists - skipping')

            except OSError as e:
                if e.errno in (errno.EEXIST, errno.ENOTDIR):
                    logger.warning(f'Failed to reconstruct {self.file_name}: {e}')

            self._check_global_completion()

    async def run_choking_loops(self) -> None:
        async def preferred_loop() -> None:
            while True:
                await asyncio.sleep(self.preferred_interval)
                interested = [ns.peer_id for ns in self.neighbors() if ns.logic.they_interested_in_us]
                selected = self.choking.select_preferred(interested, self.local_bits.count() == self.total_pieces)
                logger.info(f'has the preferred neighbors [{", ".join(str(p) for p in selected) if selected else ""}]')
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

        async def optimistic_loop() -> None:
            while True:
                await asyncio.sleep(self.optimistic_interval)
                choked_interested = [ns.peer_id for ns in self.neighbors()
                                     if ns.logic.they_interested_in_us and ns.we_choke_them]
                pick = self.choking.pick_optimistic(choked_interested)
                if pick is None:
                    continue
                logger.info(f'has the optimistically unchoked neighbor [{pick}]')
                ns = self._registry.get(pick)
                if ns and ns.logic.wire and ns.we_choke_them:
                    ns.logic.wire.send_unchoke()
                    ns.we_choke_them = False

        await asyncio.gather(preferred_loop(), optimistic_loop())

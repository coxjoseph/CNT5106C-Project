from typing import Optional
import logging
from logic.callbacks import LogicCallbacks, WireCommands
from .bitfield import Bitfield


logger = logging.getLogger(__name__)


class PeerLogic(LogicCallbacks):
    def __init__(self, node: "PeerNode"):
        self.node = node
        self.wire: Optional[WireCommands] = None
        self.peer_id: Optional[int] = None
        self._outbound: bool = False
        self.their_bits: Bitfield = Bitfield.empty(node.total_pieces)
        self.they_choke_us: bool = True
        self.they_interested_in_us: bool = False
        self._sent_bitfield: bool = False

    def set_wire(self, wire: WireCommands) -> None:
        self.wire = wire

    def mark_outbound(self, is_outbound: bool) -> None:
        self._outbound = is_outbound

    # ---- Networking callbacks ----

    def on_handshake(self, peer_id: int) -> None:
        self.peer_id = peer_id

        if self._outbound:
            logger.info(f'makes a connection to Peer [{remote_id}].')
        else:
            logger.info(f'is connected from Peer [{peer_id}].')

        self.node.register_neighbor(self)

        if not self._sent_bitfield and self.node.local_bits.count() > 0 and self.wire:
            self.wire.send_bitfield(self.node.local_bits.to_bytes())
            self._sent_bitfield = True

    def on_disconnect(self) -> None:
        self.node.on_disconnect(self)

    def on_choke(self) -> None:
        self.they_choke_us = True
        if self.peer_id is not None:
            logger.info(f'is choked by Peer [{self.peer_id}].')
            self.node.requests.clear_inflight_for_peer(self.peer_id)

    def on_unchoke(self) -> None:
        self.they_choke_us = False
        if self.peer_id is not None:
            logger.info(f'is unchoked by Peer [{self.peer_id}].')
        self.node.maybe_request_next(self)

    def on_interested(self) -> None:
        self.they_interested_in_us = True
        if self.peer_id is not None:
            logger.info(f"received the 'interested' message from Peer [{self.peer_id}].")

    def on_not_interested(self) -> None:
        self.they_interested_in_us = False
        if self.peer_id is not None:
            logger.info(f"received the 'not interested' message from Peer [{self.peer_id}].")

    def on_have(self, index: int) -> None:
        self.their_bits.set(index, True)
        if self.peer_id is not None:
            logger.info(f"received the 'have' message from Peer [{self.peer_id}] for the piece [{index}].")
        if self.their_bits.count() == self.node.total_pieces and self.peer_id is not None:
            self.node.mark_peer_complete(self.peer_id)
        self.node.recompute_interest(self)

    def on_bitfield(self, bits: bytes) -> None:
        self.their_bits = Bitfield.from_bytes(self.node.total_pieces, bits)
        if self.their_bits.count() == self.node.total_pieces and self.peer_id is not None:
            self.node.mark_peer_complete(self.peer_id)
        self.node.recompute_interest(self)

    def on_request(self, index: int) -> None:
        if self.peer_id is None or self.wire is None or self.node.we_choke_them(self.peer_id):
            return
        if self.node.store.have(index):
            data = self.node.store.read_piece(index)
            self.wire.send_piece(index, data)

    def on_piece(self, index: int, data: bytes) -> None:
        if self.peer_id is not None:
            self.node.choking.rates.add_download(self.peer_id, len(data))
        self.node.handle_piece(self, index, data)

    @property
    def sent_bitfield(self) -> bool:
        return self._sent_bitfield

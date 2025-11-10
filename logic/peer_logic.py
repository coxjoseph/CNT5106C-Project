from typing import Optional
from logic_stubs.callbacks import LogicCallbacks, WireCommands
from .bitfield import Bitfield
from net.protocol_logger import TextEventLogger


class PeerLogic(LogicCallbacks):
    """
    Per-connection logic adapter.
    """
    def __init__(self, node: "PeerNode"):
        self.node = node
        self.wire: Optional[WireCommands] = None
        self.peer_id: Optional[int] = None
        self._outbound: bool = False
        self._logger: TextEventLogger = node.logger
        self.their_bits: Bitfield = Bitfield.empty(node.total_pieces)
        self.they_choke_us: bool = True
        self.they_interested_in_us: bool = False
        self._sent_bitfield: bool = False

    def set_wire(self, wire: WireCommands) -> None:
        self.wire = wire

    def mark_outbound(self, is_outbound: bool) -> None:
        self._outbound = is_outbound

    # ---- Networking callbacks ----

    def on_handshake(self, peer_id: int):
        self.peer_id = peer_id

        if self._outbound:
            self._logger.makes_connection_to(peer_id)
        else:
            self._logger.connected_from(peer_id)
        # Register this neighbor with the node
        self.node.register_neighbor(self)
        # Send our bitfield if we have any pieces and haven't sent it yet
        if not self._sent_bitfield and self.node.local_bits.count() > 0 and self.wire:
            self.wire.send_bitfield(self.node.local_bits.to_bytes())
            self._sent_bitfield = True

    def on_disconnect(self):
        self.node.on_disconnect(self)

    def on_choke(self):
        self.they_choke_us = True
        # Cancel any inflight request assigned to this neighbor
        if self.peer_id is not None:
            self._logger.choked_by(self.peer_id)
            self.node.requests.clear_inflight_for_peer(self.peer_id)

    def on_unchoke(self):
        self.they_choke_us = False
        if self.peer_id is not None:
            self._logger.unchoked_by(self.peer_id)
        self.node.maybe_request_next(self)

    def on_interested(self):
        self.they_interested_in_us = True
        if self.peer_id is not None:
            self._logger.received_interested(self.peer_id)

    def on_not_interested(self):
        self.they_interested_in_us = False
        if self.peer_id is not None:
            self._logger.received_not_interested(self.peer_id)

    def on_have(self, index: int):
        self.their_bits.set(index, True)
        if self.peer_id is not None:
            self._logger.received_have(self.peer_id, index)
        if self.their_bits.count() == self.node.total_pieces and self.peer_id is not None:
            self.node.mark_peer_complete(self.peer_id)
        self.node.recompute_interest(self)

    def on_bitfield(self, bits: bytes):
        self.their_bits = Bitfield.from_bytes(self.node.total_pieces, bits)
        if self.their_bits.count() == self.node.total_pieces and self.peer_id is not None:
            self.node.mark_peer_complete(self.peer_id)
        self.node.recompute_interest(self)

    def on_request(self, index: int):
        # Serve only if we are unchoking them and we have the piece
        if self.peer_id is None or self.wire is None or self.node.we_choke_them(self.peer_id):
            return
        if self.node.store.have(index):
            data = self.node.store.read_piece(index)
            self.wire.send_piece(index, data)

    def on_piece(self, index: int, data: bytes):
        if self.peer_id is not None:
            self.node.choking.rates.add_download(self.peer_id, len(data))
        self.node.handle_piece(self, index, data)

    @property
    def sent_bitfield(self):
        return self._sent_bitfield

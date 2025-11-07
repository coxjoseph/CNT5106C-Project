from logic_stubs.callbacks import LogicCallbacks, WireCommands
from typing import Optional

class PeerLogic(LogicCallbacks):
    def __init__(self):
        self.wire: Optional[WireCommands] = None
        self.sent_handshake: bool = False

    def set_wire(self, wire: WireCommands) -> None:
        self.wire = wire

    def on_handshake(self, peer_id: int):
        if not self.sent_handshake:
            self.wire.send_handshake(peer_id)
            self.sent_handshake = True
        self.wire.send_bitfield()

    def on_disconnect(self):
        se

"""
Small scripted "logic" section so that network code can be demoed/tested without
implementation of logic

    Behavior:
    - "server" side: on handshake, send a small bitfield; on interested, unchoke;
      on request(i), send a tiny piece(i, b"hello").
    - "client" side: on bitfield, send interested; on unchoke, request piece 0;
      on piece, print and close.
"""

from typing import Optional
from .callbacks import LogicCallbacks, WireCommands


class DummyLogic(LogicCallbacks):
    def __init__(self, role: str):
        assert role in ["server", "client"]
        self.role = role
        self.wire: Optional[WireCommands] = None
        self.seen_piece: bool = False

    def set_wire(self, wire: WireCommands) -> None:
        self.wire = wire

    def on_handshake(self, peer_id: int) -> None:
        print(f'{self.role} received handshake from peer {peer_id}')
        if self.role == "server" and self.wire:
            print('server sending bitfield...')
            self.wire.send_bitfield(b'\x80')

    def on_disconnect(self) -> None:
        pass

    def on_choke(self) -> None:
        pass

    def on_unchoke(self) -> None:
        # Client always requests
        if self.role == "client" and self.wire:
            print('[client] unchoked... requesting piece')
            self.wire.send_request(0)

    def on_interested(self) -> None:
        # Server always unchokes
        if self.role == "server" and self.wire:
            print("[server] unchoking client")
            self.wire.send_unchoke()

    def on_not_interested(self) -> None:
        pass

    def on_have(self, index: int) -> None:
        pass

    def on_bitfield(self, bits: bytes) -> None:
        # Client sends an interested message no matter what
        if self.role == "client" and self.wire:
            print('[client] received bitfield, sending interested...')
            self.wire.send_interested()

    def on_request(self, index: int) -> None:
        if self.role == "server" and self.wire:
            print('[server] sending piece!...')
            self.wire.send_piece(index, b"hello")

    def on_piece(self, index: int, data: bytes) -> None:
        print(f"[client] received piece {index}: {data!r}")
        if self.wire and not self.seen_piece:
            self.seen_piece = True
            self.wire.close()

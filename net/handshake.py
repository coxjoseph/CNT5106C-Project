import struct
from .constants import HEADER, ZEROS


class Handshake:
    __slots__ = ('peer_id',)

    def __init__(self, peer_id: int):
        self.peer_id = int(peer_id)

    def encode(self) -> bytes:
        return HEADER + ZEROS + struct.pack('>I', self.peer_id)

    @staticmethod
    def decode(buf: bytes) -> 'Handshake':
        if len(buf) < 18 + 10 + 4:
            raise ValueError('Handshake too small')
        if buf[:18] != HEADER:
            raise ValueError('Handshake header not valid')
        if buf[18:28] != ZEROS:
            raise ValueError('Handshake padding not valid')

        (peer_id,) = struct.unpack('>I', buf[28:])
        return Handshake(peer_id)

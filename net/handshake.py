import struct
from .constants import HEADER, ZEROS,


class Handshake:
    __slots__ = ('peer_id',)

    def __init__(self, peer_id: int):
        self.peer_id = int(peer_id)  # just in case

    def encode(self) -> bytes:
        return HEADER + ZEROS + struct.pack('>I', self.peer_id)

    @staticmethod
    def decode(buf: bytes) -> 'Handshake':
        if len(buf) < 16 + 10 + 4:
            raise ValueError('Handshake too smol :(')
        if buf[:16] != HEADER:
            raise ValueError('Bad handshake header :(')
        if buf[16:26] != ZEROS:
            raise ValueError('Bad handshake padding :(')

        (peer_id,) = struct.unpack('>I', buf[26:30])
        return Handshake(peer_id)


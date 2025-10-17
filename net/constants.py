from enum import IntEnum

HEADER = b'P2PFILESHARINGPRO'
ZEROS = b'\x00' * 10
MAX_FRAME = 10 * 1024 * 1024


class MessageType(IntEnum):
    CHOKE = 0
    UNCHOKE = 1
    INTERESTED = 2
    NOT_INTERESTED = 3
    HAVE = 4
    BITFIELD = 5
    REQUEST = 6
    PIECE = 7


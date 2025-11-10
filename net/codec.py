import struct
from typing import Optional
from .constants import MessageType, MAX_FRAME


# Frames: LEN(4B, big-endian) | TYPE(1B) | PAYLOAD(LEN-1)
def encode_frame(msg_type: MessageType, payload: bytes = b'') -> bytes:
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("Payload isn't bytes-like - panic")
    length = 1 + len(payload)
    return struct.pack('>I', length) + struct.pack('>B', int(msg_type)) + payload


def decode_one(buffer: bytearray) -> Optional[tuple[MessageType, bytes]]:
    # no payload
    if len(buffer) < 4:
        return None

    (length,) = struct.unpack('>I', buffer[:4])
    if length <= 0 or length > MAX_FRAME:
        raise ValueError(f'frame is a long boye, size {length}')

    if len(buffer) < 4 + length:
        return None

    mtype = MessageType(buffer[4])
    payload = bytes(buffer[5:4 + length])

    del buffer[:4 + length]
    return mtype, payload


# Helpers
def enc_have(index: int) -> bytes: return struct.pack('>I', index)


def dec_have(payload: bytes) -> int:
    if len(payload) != 4:
        raise ValueError('Expected 4B in HAVE message')
    return struct.unpack('>I', payload)[0]


def enc_request(index: int) -> bytes: return struct.pack('>I', index)


def dec_request(payload: bytes) -> int:
    if len(payload) != 4:
        raise ValueError('Expected 4B in REQUEST message')
    return struct.unpack('>I', payload)[0]


def enc_piece(index: int, data: bytes) -> bytes: return struct.pack('>I', index) + data


def dec_piece(payload: bytes) -> tuple[int, bytes]:
    index = struct.unpack('>I', payload[:4])[0]
    return index, payload[4:]

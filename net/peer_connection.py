import asyncio
from typing import Optional
from .constants import MessageType
from .handshake import Handshake
from .codec import (
    encode_frame, decode_one,
    enc_have, dec_have,
    enc_request, dec_request,
    enc_piece, dec_piece
)

from logic_stubs.callbacks import WireCommands, LogicCallbacks


class PeerConnection(WireCommands):
    def __init__(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
            callbacks: LogicCallbacks,
            local_peer_id: int,
            handshake_timeout: float = 5.0,
            idle_timeout: Optional[float] = None,
    ):
        self._r = reader
        self._w = writer
        self._cb = callbacks
        self._local_id = int(local_peer_id)
        self.connected_peer_id = None
        self._hshake_to = handshake_timeout
        self._idle_to = idle_timeout
        self._read_task: Optional[asyncio.Task] = None
        self._buf = bytearray()
        self._closed = False

    async def start(self) -> None:
        self.send_handshake(self._local_id)

        try:
            remote = await asyncio.wait_for(self._r.readexactly(32), timeout=self._hshake_to)  # expect 32b handshake
        except Exception as e:
            self._safe_disconnect()
            return

        # decode, break
        try:
            hs = Handshake.decode(remote)
            self.connected_peer_id = hs.peer_id
        except Exception:
            self._safe_disconnect()
            return

        # run whatever happens on handshake
        try:
            self._cb.on_handshake(hs.peer_id)
        except Exception:
            pass
        self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        try:
            while not self._closed:
                chunk = await self._r.read(4096)
                if not chunk:
                    break
                self._buf.extend(chunk)
                while True:
                    res = decode_one(self._buf)
                    if res is None:
                        break
                    mtype, payload = res
                    self._dispatch(mtype, payload)
        except Exception:
            pass
        finally:
            self._safe_disconnect()

    def _dispatch(self, mtype: MessageType, payload: bytes) -> None:
        try:
            if mtype == MessageType.CHOKE:
                self._cb.on_choke()
            elif mtype == MessageType.UNCHOKE:
                self._cb.on_unchoke()
            elif mtype == MessageType.INTERESTED:
                self._cb.on_interested()
            elif mtype == MessageType.NOT_INTERESTED:
                self._cb.on_not_interested()
            elif mtype == MessageType.HAVE:
                self._cb.on_have(dec_have(payload))
            elif mtype == MessageType.BITFIELD:
                self._cb.on_bitfield(payload)
            elif mtype == MessageType.REQUEST:
                self._cb.on_request(dec_request(payload))
            elif mtype == MessageType.PIECE:
                idx, data = dec_piece(payload)
                self._cb.on_piece(idx, data)
        except Exception:
            pass

    # -- implementation of protocol --
    def send_handshake(self, peer_id: int) -> None:
        if self._closed: return
        try:
            self._w.write(Handshake(peer_id).encode())
        except Exception:
            self._safe_disconnect()

    def send_choke(self) -> None:
        self._send_t(MessageType.CHOKE)

    def send_unchoke(self) -> None:
        self._send_t(MessageType.UNCHOKE)

    def send_interested(self) -> None:
        self._send_t(MessageType.INTERESTED)

    def send_not_interested(self) -> None:
        self._send_t(MessageType.NOT_INTERESTED)

    def send_have(self, index: int) -> None:
        self._send_tp(MessageType.HAVE, enc_have(index))

    def send_bitfield(self, bits: bytes) -> None:
        if not isinstance(bits, (bytes, bytearray)):
            raise TypeError('bitfield must be bytes')
        self._send_tp(MessageType.BITFIELD, bytes(bits))

    def send_request(self, index: int) -> None:
        self._send_tp(MessageType.REQUEST, enc_request(index))

    def send_piece(self, index: int, data: bytes) -> None:
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError('piece data must be bytes')
        self._send_tp(MessageType.PIECE, enc_piece(index, bytes(data)))

    def close(self) -> None:
        self._safe_disconnect()

    # helpers
    def _send_t(self, t: MessageType) -> None:
        if self._closed: return
        try:
            self._w.write(encode_frame(t))
        except Exception:
            self._safe_disconnect()

    def _send_tp(self, t: MessageType, p: bytes) -> None:
        if self._closed: return
        try:
            self._w.write(encode_frame(t, p))
        except Exception:
            self._safe_disconnect()

    def _safe_disconnect(self) -> None:
        if self._closed: return
        self._closed = True
        try:
            self._w.close()
        except Exception:
            pass
        try:
            self._cb.on_disconnect()
        except Exception:
            pass

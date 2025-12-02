import asyncio
from typing import Optional
import logging
from .constants import MessageType
from .handshake import Handshake
from .codec import (
    encode_frame, decode_one,
    enc_have, dec_have,
    enc_request, dec_request,
    enc_piece, dec_piece
)

from logic.callbacks import WireCommands, LogicCallbacks

logger = logging.getLogger(__name__)


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
        self._handshake_to = handshake_timeout
        self._idle_to = idle_timeout
        self._read_task: Optional[asyncio.Task] = None
        self._buf = bytearray()
        self._closed = False

    async def start(self) -> None:
        self.send_handshake(self._local_id)

        try:
            remote = await asyncio.wait_for(self._r.readexactly(32), timeout=self._handshake_to)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError, OSError) as e:
            logger.warning(f'Handshake failed: {e}')
            self._safe_disconnect()
            return

        try:
            hs = Handshake.decode(remote)
            self.connected_peer_id = hs.peer_id
        except (ValueError, OSError) as e:
            logger.warning(f'Failed to decode handshake: {e}')
            self._safe_disconnect()
            return

        try:
            self._cb.on_handshake(hs.peer_id)
        except (AttributeError, RuntimeError, TypeError) as e:
            logger.error(f'Error running handshake callback for peer {hs.peer_id}: {e}')
        self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        try:
            while not self._closed:
                chunk = None
                try:
                    chunk = await self._r.read(4096)
                except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError, OSError) as e:
                    logger.warning(f'Read error: {e}')

                if not chunk:
                    break
                self._buf.extend(chunk)

                while True:
                    res = None
                    try:
                        res = decode_one(self._buf)
                    except ValueError as e:
                        logger.warning(f'Failed to decode frame: {e}')
                    if res is None:
                        break
                    mtype, payload = res
                    try:
                        self._dispatch(mtype, payload)
                    except (ValueError, RuntimeError, TypeError) as e:
                        logger.warning(f'Error dispatching message: {e}')
        except asyncio.CancelledError as e:
            logger.debug(f'Read loop cancelled: {e}')
        finally:
            self._safe_disconnect()

    def _dispatch(self, mtype: MessageType, payload: bytes) -> None:
        try:
            match mtype:
                case MessageType.CHOKE:
                    self._cb.on_choke()
                case MessageType.UNCHOKE:
                    self._cb.on_unchoke()
                case MessageType.INTERESTED:
                    self._cb.on_interested()
                case MessageType.NOT_INTERESTED:
                    self._cb.on_not_interested()
                case MessageType.HAVE:
                    self._cb.on_have(dec_have(payload))
                case MessageType.BITFIELD:
                    self._cb.on_bitfield(payload)
                case MessageType.REQUEST:
                    self._cb.on_request(dec_request(payload))
                case MessageType.PIECE:
                    idx, data = dec_piece(payload)
                    self._cb.on_piece(idx, data)
                case _:
                    logger.warning(f'Unknown message type: {mtype}')
        except (ValueError, AttributeError, RuntimeError, TypeError) as e:
            logger.warning(f'Error dispatching message {mtype.name}: {e}')

    def send_handshake(self, peer_id: int) -> None:
        if self._closed:
            return
        try:
            self._w.write(Handshake(peer_id).encode())
        except (OSError, ConnectionError, ValueError) as e:
            logger.warning(f'Failed to send handshake to peer {peer_id}: {e}')
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

    def _send_t(self, t: MessageType) -> None:
        if self._closed:
            return
        try:
            self._w.write(encode_frame(t))
        except ValueError as e:
            logger.error(f'Failed to encode frame for {t.name}: {e}')
            self._safe_disconnect()
        except (ConnectionError, OSError) as e:
            logger.warning(f'Write error for {t.name}: {e}')
            self._safe_disconnect()

    def _send_tp(self, t: MessageType, p: bytes) -> None:
        if self._closed:
            return
        try:
            self._w.write(encode_frame(t, p))
        except ValueError as e:
            logger.error(f'Failed to encode frame for {t.name} with payload ({len(p)}B): {e}')
            self._safe_disconnect()
        except (ConnectionError, OSError) as e:
            logger.warning(f'Write error for {t.name} with payload ({len(p)}B): {e}')
            self._safe_disconnect()

    def _safe_disconnect(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._w.close()
            logger.info(f"has closed the connection to peer [{self.connected_peer_id}]")
        except OSError as e:
            logger.warning(f'Error while closing writer: {e}')
        try:
            self._cb.on_disconnect()
        except (AttributeError, RuntimeError, TypeError) as e:
            logger.debug(f'on_disconnect callback error: {e}')

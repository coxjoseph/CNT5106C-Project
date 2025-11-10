import asyncio
import logging
from typing import Callable, Optional, Set

from logic_stubs.callbacks import LogicCallbacks
from .peer_connection import PeerConnection

logger = logging.getLogger(__name__)


class Connector:
    def __init__(
        self,
        listen_host: str,
        listen_port: int,
        *,
        local_peer_id: int,
        logic_factory: Callable[[], LogicCallbacks],
        handshake_timeout: float = 5.0,
    ):
        self._listen_host = listen_host
        self._listen_port = int(listen_port)
        self._local_peer_id = int(local_peer_id)
        self._logic_factory = logic_factory
        self._handshake_to = float(handshake_timeout)

        self._server: Optional[asyncio.base_events.Server] = None
        self._tasks: Set[asyncio.Task] = set()
        self._connections: Set[PeerConnection] = set()
        self._closing = False

    async def serve(self) -> None:
        self._server = await asyncio.start_server(self._on_client, self._listen_host, self._listen_port)
        async with self._server:
            await self._server.serve_forever()

    async def connect(self, host: str, port: int) -> None:
        reader, writer = await asyncio.open_connection(host, port)
        logic = self._logic_factory()
        if hasattr(logic, 'mark_outbound'):
            logic.mark_outbound(True)
        await self._start_connection(reader, writer)

    async def connect_with_retry(
        self,
        host: str,
        port: int,
        *,
        attempts: int = 5,
        initial_backoff: float = 1.0,
        max_backoff: float = 10.0,
    ) -> None:
        backoff = float(initial_backoff)
        for _ in range(max(1, attempts)):
            try:
                await self.connect(host, port)
                return
            except (ConnectionError, asyncio.TimeoutError, OSError) as e:
                logger.warning(f'Connection attempt to {host}:{port} failed: {e}')
                await asyncio.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)

    async def close_all(self) -> None:
        if self._closing:
            return
        self._closing = True

        if self._server is not None:
            self._server.close()
            try:
                await self._server.wait_closed()
            except OSError as e:
                logger.warning(f'Error while closing socket: {e}')
            self._server = None

        for conn in list(self._connections):
            try:
                conn.close()
            except OSError as e:
                logger.warning(f'Error while closing connection {conn}: {e}')

        for t in list(self._tasks):
            if not t.done():
                t.cancel()
        await asyncio.sleep(0)

    async def _on_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        logic = self._logic_factory()
        if hasattr(logic, 'mark_outbound'):
            logic.mark_outbound(False)
        await self._start_connection(reader, writer)

    async def _start_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        logic = self._logic_factory()
        conn = PeerConnection(
            reader,
            writer,
            callbacks=logic,
            local_peer_id=self._local_peer_id,
            handshake_timeout=self._handshake_to,
        )
        if hasattr(logic, 'set_wire'):
            logic.set_wire(conn)

        self._connections.add(conn)
        task = asyncio.create_task(self._run_connection(conn))
        self._track_task(task)

    async def _run_connection(self, conn: PeerConnection) -> None:
        try:
            await conn.start()
            while True:
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            logger.debug(f'Connection for task {conn} was cancelled')
        except (ConnectionError, OSError, asyncio.TimeoutError) as e:
            logger.warning(f'Error during connection handling to {conn}: {e}')
        finally:
            try:
                conn.close()
            except OSError as e:
                logger.warning(f'Error closing connection {conn}: {e}')
            self._connections.discard(conn)

    def _track_task(self, task: asyncio.Task) -> None:
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

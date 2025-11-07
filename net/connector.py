import asyncio
from typing import Callable, Optional, Set

from logic_stubs.callbacks import LogicCallbacks
from .peer_connection import PeerConnection


class Connector:
    """
    Networking glue:
      - Owns the single listening socket (asyncio.start_server)
      - Makes outbound connections (asyncio.open_connection)
      - For each connection: creates LogicCallbacks via logic_factory,
        wires it to a PeerConnection, and starts the protocol.
    """

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
        self._hshake_to = float(handshake_timeout)

        self._server: Optional[asyncio.base_events.Server] = None
        self._tasks: Set[asyncio.Task] = set()
        self._connections: Set[PeerConnection] = set()
        self._closing = False

    # ----------------------------- public API ------------------------------

    async def serve(self) -> None:
        """Start the listener and serve forever (until cancelled/closed)."""
        self._server = await asyncio.start_server(self._on_client, self._listen_host, self._listen_port)
        async with self._server:
            await self._server.serve_forever()

    async def connect(self, host: str, port: int) -> None:
        """Open an outbound connection and start its PeerConnection."""
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
        """Outbound connect with simple exponential backoff."""
        backoff = float(initial_backoff)
        for _ in range(max(1, attempts)):
            try:
                await self.connect(host, port)
                return
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)

    async def close_all(self) -> None:
        """Stop accepting, close all connections, cancel handler tasks."""
        if self._closing:
            return
        self._closing = True

        if self._server is not None:
            self._server.close()
            try:
                await self._server.wait_closed()
            except Exception:
                pass
            self._server = None

        for conn in list(self._connections):
            try:
                conn.close()
            except Exception:
                pass

        for t in list(self._tasks):
            if not t.done():
                t.cancel()
        await asyncio.sleep(0)

    # ---------------------------- internals --------------------------------

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
            handshake_timeout=self._hshake_to,
        )
        if hasattr(logic, "set_wire"):
            logic.set_wire(conn)

        self._connections.add(conn)
        task = asyncio.create_task(self._run_connection(conn))
        self._track_task(task)

    async def _run_connection(self, conn: PeerConnection) -> None:
        try:
            await conn.start()
            # keep task alive until the connection closes
            while True:
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
            self._connections.discard(conn)

    def _track_task(self, task: asyncio.Task) -> None:
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
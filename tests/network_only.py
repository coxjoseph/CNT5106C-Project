import argparse
import asyncio
from logic_stubs.dummy_logic import DummyLogic
from net.peer_connection import PeerConnection


async def run_server(host: str, port: int, peer_id: int):
    async def handler(reader, writer):
        logic = DummyLogic(role="server")
        conn = PeerConnection(reader, writer, callbacks=logic, local_peer_id=peer_id)
        logic.set_wire(conn)
        await conn.start()
    server = await asyncio.start_server(handler, host, port)
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    print(f"[server] listening on {addrs}")
    async with server:
        await server.serve_forever()

async def run_client(host: str, port: int, peer_id: int):
    reader, writer = await asyncio.open_connection(host, port)
    logic = DummyLogic(role="client")
    conn = PeerConnection(reader, writer, callbacks=logic, local_peer_id=peer_id)
    logic.set_wire(conn)
    await conn.start()
    while True:
        await asyncio.sleep(0.1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["server", "client"], required=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--peer-id", type=int, default=1)
    args = ap.parse_args()
    if args.mode == "server":
        asyncio.run(run_server(args.host, args.port, args.peer_id))
    else:
        asyncio.run(run_client(args.host, args.port, args.peer_id))

if __name__ == "__main__":
    main()

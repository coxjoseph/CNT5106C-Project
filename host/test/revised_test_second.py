import asyncio
from host.peer_revision import PeerRevised


async def main():
    test_peer = PeerRevised(1002, "localhost", 22222, bytes(),
                            1, 1, 1,1,
                            True,"RevisedTest2.log")

    await test_peer.connect(("localhost", 11111), 1001)

    print(test_peer.peer_info)

asyncio.run(main())
import asyncio
from host.peer_revision import PeerRevised
from time import sleep


async def main():
    test_peer = PeerRevised(1001, "localhost", 11111, bytes(),
                            1, 1, 1,1,
                            True,"RevisedTest1.log")
    try:
        await test_peer.start()
        await test_peer.listen()
    except KeyboardInterrupt:
        pass
    finally:
        print(test_peer.peer_info)


asyncio.run(main())
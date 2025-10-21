from time import sleep
from host.host import Host

def main():
    iters = 1000
    server_test = Host("1001", "localhost", 12345,
                       0, 1, 1, 1, 1)

    while not server_test.listen("1002") and iters:
        iters -= 1
        sleep(0.1)

    if iters:
        server_test.send("1002", b"CONNECTED!")

        response = None
        while not response:
            response = server_test.recv(1024)
        print(f"RECEIVED RESPONSE: {response[0].decode()} from {response[1][0]}:{response[1][1]}")

        server_test.close()

if __name__ == "__main__":
    main()

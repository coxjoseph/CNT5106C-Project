from time import sleep
from host.host import Host

def main():
    iters = 100
    client_test = Host("1002", "localhost", 22222,
                       0, 1, 1, 1, 1)

    while not client_test.connect(("localhost", 12345), "1001") and iters:
        iters -= 1
        sleep(0.1)

    if iters:
        response = None
        while not response:
            response = client_test.recv(1024)
        print(f"RECEIVED RESPONSE: {response[0].decode()} from {response[1][0]}:{response[1][1]}")

        client_test.send("1001", response[0] + b" " + response[0])

        client_test.close()


main()
import socket


class Host:
    def __init__(self, name, ip_address, listening_port_number, bitfield, max_connections,
                 num_preferred_peers, unchoke_interval, optimistic_unchoke_interval,
                 verbose=False, log_file="", time_format="%m/%d/%Y :: %H:%M:%S.%f"):

        self.name = name
        self.ip_address = ip_address
        self.listening_port_number = listening_port_number
        self.bitfield = bitfield  # array ?
        self.pieces_locations = dict({})  # pieces_location[piece_no] = file_location_on_disc
        self.verbose = verbose
        self.time_format = time_format

        self.num_connected_peers = 0

        self.max_connections = max_connections
        self.num_preferred_peers = num_preferred_peers  # k, determined by config
        self.unchoke_interval = unchoke_interval  # p, determined by config
        self.optimistic_unchoke_interval = optimistic_unchoke_interval  # m, determined by config

        if verbose and not log_file:
            raise FileNotFoundError("Missing arg 'log_file' while in verbose mode!")
        self.log_file = log_file

        # stores info about peers, initialize dictionary on initial connection
        # field stored in peer_info[peer_id][field]
        # e.g., the unchoke status of peer 1001 is at peer_info[1001]["unchoked"]
        self.peer_info = dict({})
        ###
        # fields are:
        #       - ip_address: string, peer ip address
        #       - port_number: string, peer process port number
        #       - full_address: tuple, (ip_address, port_number)
        #       - connection_socket: socket returned by s.accept when forming connection
        #                            or socket created to connect to peer
        #       - peer_number: used by the bitfield to determine what row of the bitfield corresponds to the peer
        #       - unchoked: boolean, true if currently sending data to peer
        #       - preferred: boolean, true if currently a preferred peer
        #       - download_rate: integer, number of bytes received from peer during preferred neighbor calculation cycle
        #       - next_seq_number: next sequence number to send to peer
        #       - last_ack_byte: last byte acknowledged by the peer
        #       - last_recv_byte: last byte acknowledged by this host sent from the peer
        #       - average_rtt: average RTT for messages with this peer
        #       - stdev_rtt: standard deviation of RTTs for messages with this peer
        #       - timeout_interval: calculated as average_rtt + 4 * stdev_rtt, timeout interval
        #                           for communications with peer
        #       - last_piece_sent: piece that is currently being sent to peer, may be partially incomplete if preferred
        #                          neighbors change during sending process
        #       - last_piece_received: piece currently expected from peer, may be partially incomplete if preferred
        #                              neighbors change during reception process
        ###

        # do NOT use `with Host.listening_socket as s:` for connection calls
        # because it will automatically close the socket
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.bind((self.ip_address, self.listening_port_number))

    def connect(self, address:tuple, peer_id:str, timeout:float=0.500) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        old_timeout = s.gettimeout()
        s.settimeout(timeout)

        try:
            s.connect(address)
            connection_formed = True

            # store connection details
            conn_details = dict({})
            conn_details["ip_address"] = address[0]
            conn_details["port_numer"] = address[1]
            conn_details["full_address"] = address
            conn_details["connection_socket"] = s
            conn_details["unchoked"] = False
            conn_details["preferred"] = False
            conn_details["download_rate"] = False
            conn_details["average_rtt"] = 0
            conn_details["stdev_rtt"] = 0

            self.peer_info[peer_id] = conn_details
            self.num_connected_peers += 1

        except socket.timeout:
            print(f"Failed to connect to: {address}")
            connection_formed = False

        s.settimeout(old_timeout)

        return connection_formed

    def listen(self, peer_id, timeout:float=0.500) -> bool:

        old_timeout = self.listening_socket.gettimeout()
        self.listening_socket.settimeout(timeout)

        try:
            self.listening_socket.listen(self.max_connections)
            conn, addr = self.listening_socket.accept()

            # Exception caught if connection not formed
            found_connection = True

            # store connection details
            conn_details = dict({})
            conn_details["ip_address"] = addr[0]
            conn_details["port_numer"] = addr[1]
            conn_details["full_address"] = addr
            conn_details["connection_socket"] = conn
            conn_details["unchoked"] = False
            conn_details["preferred"] = False
            conn_details["download_rate"] = False
            conn_details["average_rtt"] = 0
            conn_details["stdev_rtt"] = 0

            self.peer_info[peer_id] = conn_details
            self.num_connected_peers += 1


        except socket.timeout:
            print(f"Failed to find client trying to connect.")
            found_connection = False

            self.listening_socket.settimeout(old_timeout)

        return found_connection

    def send(self, peer_id, msg):
        sent_bytes = 0

        c: socket.socket = self.peer_info[peer_id]["connection_socket"]
        if isinstance(msg, str):
            msg = msg.encode()
        while sent_bytes < len(msg):
            # may want to append header on each iteration
            sent_bytes += c.send(msg[sent_bytes:])

    def recv(self, buffer_size) -> tuple[bytes, tuple]:
        for peer in self.peer_info.keys():
            try:
                s: socket.socket = self.peer_info[peer]["connection_socket"]
                old_blocking = s.getblocking()
                s.setblocking(False)
                msg = s.recv(buffer_size)
                s.setblocking(old_blocking)
            except BlockingIOError:
                msg = None

            if msg:
                msg = (msg, self.peer_info[peer]["full_address"])
                break

        return msg

    def close(self):
        self.listening_socket.close()
        for peer in self.peer_info.keys():
            self.peer_info[peer]["connection_socket"].close()
import socket


class Host:
    def __init__(self, name, ip_address, port_number, bitfield, max_connections,
                 num_preferred_peers, unchoke_inteval, optimistic_unchoke_interval,
                 verbose=False, log_file="", time_format="%m/%d/%Y :: %H:%M:%S.%f"):

        self.name = name
        self.ip_address = ip_address
        self.port_number = port_number
        self.bitfield = bitfield  # array ?
        self.pieces_locations = dict({})  # pieces_location[piece_no] = file_location_on_disc
        self.verbose = verbose
        self.time_format = time_format

        self.num_connected_peers = 0

        self.max_connections = max_connections
        self.num_preferred_peers = num_preferred_peers  # k, determined by config
        self.unchoke_interval = unchoke_inteval  # p, determined by config
        self.optimistic_unchoke_interval = optimistic_unchoke_interval  # m, determined by config

        if verbose and not log_file:
            raise FileNotFoundError("Missing arg 'log_file' while in verbose mode!")
        self.log_file = log_file

        # stores info about peers, initialize dictionary on initial connection
        # field stored in peer_info[peer_ip_address:port_number][field]
        # e.g., the unchoke status of peer @ 168.0.0.0:300 is at peer_ip_address:port_number][unchoked]
        self.peer_info = dict({})
        ###
        # fields are:
        #       - ip_address: string, peer ip address, used as combo with port_number as key
        #       - port_number: string, peer process port number, used as combo with ip_address as key
        #       - connection_socket: socket returned by s.accept() when forming connection
        #       - connection_string: address returned by s.accept() when forming connection
        #       - peer_number: used by the bitfield to determine what row of the bitfield corresponds to the peer
        #       - peer_name: string, determined by config file, useful for debugging
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

        # use `with Host.socket as s:` for all connection calls
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.ip_address, self.port_number))

    def connect(self, address:tuple, timeout:float=500) -> bool:
        with self.socket as s:
            old_timeout = s.timeout
            s.settimeout(timeout)

            try:
                s.connect(address)
                connection_formed = True

                # add connection details

            except TimeoutError:
                print(f"Failed to connect to: {address}")
                connection_formed = False

            s.settimeout(old_timeout)

        return connection_formed


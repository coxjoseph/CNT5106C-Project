import asyncio
from net.peer_connection import PeerConnection
from logic_stubs.callbacks import LogicCallbacks
import logging

class PeerRevised:
    def __init__(self, peer_id:int, ip_address:str, listening_port_number:int, bitfield:bytes, max_connections:int,
                 num_preferred_peers:int, unchoke_interval:float, optimistic_unchoke_interval:float,
                 verbose:bool=False, log_file:str="",
                 log_header_format:str="%(asctime)s :: %(name)s :: %(levelname)s :: %(message)s"):

        self.peer_id:int = peer_id
        self.ip_address:str = ip_address
        self.listening_port_number:int = listening_port_number

        # need to run start() after initialization to use as server
        self.listening_socket:asyncio.Server = None

        self.bitfield:bytes = bitfield
        self.pieces_locations:dict = dict({})  # pieces_location[piece_no] = file_location_on_disc
        self.verbose:bool = verbose

        self.num_connected_peers:int = 0

        self.max_connections:int = max_connections
        self.num_preferred_peers:int = num_preferred_peers  # k, determined by config
        self.unchoke_interval:float = unchoke_interval  # p, determined by config
        self.optimistic_unchoke_interval:float = optimistic_unchoke_interval  # m, determined by config

        if verbose:
            if not log_file:
                raise FileNotFoundError("Missing arg 'log_file' while in verbose mode!")
            else:
                logging.basicConfig(filename=log_file, format=log_header_format, level=logging.INFO, filemode='w')
                self.logger = logging.getLogger(f"HOST:{self.peer_id}")

        # stores info about peers, initialize dictionary on initial connection
        # field stored in peer_info[peer_id][field]
        # e.g., the unchoke status of peer 1001 is at peer_info[1001]["unchoked"]
        self.peer_info = dict({})
        ###
        # fields are:
        #       - ip_address: string, peer ip address
        #       - port_number: string, peer process port number
        #       - full_address: tuple, (ip_address, port_number)
        #       - connection: PeerConnection object for handling formal connection messages
        #       - reader: asyncio StreamReader object which will receive messages from the peer
        #       - writer: asyncio StreamWriter object which will send messages to the peer
        #       - peer_number: used by the bitfield to determine what row of the bitfield corresponds to the peer
        #       - unchoked: boolean, true if currently sending data to peer
        #       - preferred: boolean, true if currently a preferred peer
        #       - download_rate: integer, number of bytes received from peer during preferred neighbor calculation cycle
        #       - last_recv_byte: last byte acknowledged by this host sent from the peer
        #       - last_piece_sent: piece that is currently being sent to peer, may be partially incomplete if preferred
        #                          neighbors change during sending process
        #       - last_piece_received: piece currently expected from peer, may be partially incomplete if preferred
        #                              neighbors change during reception process
        ###

    async def start(self):
        if self.verbose:
            self.logger.info(f"Starting server at {self.ip_address}:{self.listening_port_number}...")

        self.listening_socket = \
            await asyncio.start_server(self.connected_to, self.ip_address, self.listening_port_number,
                                       limit=self.max_connections)

        if self.verbose:
            self.logger.info(f"Started server at {self.ip_address}:{self.listening_port_number}.")

    async def listen(self):
        if self.verbose:
            self.logger.info(f"Listening at {self.ip_address}:{self.listening_port_number}...")
        async with self.listening_socket:
            await self.listening_socket.serve_forever()


    # connect to a process with given address, assigned to be
    async def connect(self, address:tuple):

        if self.verbose:
            self.logger.info(f"Connecting to peer at {address[0]}:{address[1]}...")

        reader, writer = await asyncio.open_connection(address[0], address[1])

        if self.verbose:
            self.logger.info(f"Connected to peer at {address[0]}:{address[1]}.")

        # store connection details
        conn_details = dict({})

        conn_details["ip_address"] = address[0]
        conn_details["port_number"] = address[1]
        conn_details["full_address"] = address
        conn_details["reader"] = reader
        conn_details["writer"] = writer


        if self.verbose:
            self.logger.info(f"Starting communication with peer at {address[0]}:{address[1]}.")

        connection = PeerConnection(reader, writer, LogicCallbacks, self.peer_id)
        conn_details["connection"] = connection
        await connection.start()

        conn_details["unchoked"] = False
        conn_details["preferred"] = False
        conn_details["download_rate"] = 0

        if self.verbose:
            self.logger.info(f"Formal communication with peer {connection.connected_peer_id} "
                             f"({address[0]}:{address[1]}) beginning.")

        self.peer_info[connection.connected_peer_id] = conn_details
        self.num_connected_peers += 1


    # when connected to, form connection back and cache details
    async def connected_to(self, reader:asyncio.StreamReader, writer:asyncio.StreamWriter):
        conn_details = dict({})

        address = writer.get_extra_info('peername')
        ip_address = address[0]
        port = ip_address[1]
        conn_details["address"] = (ip_address, port)
        conn_details["ip_address"] = ip_address
        conn_details["port_number"] = port

        if self.verbose:
            self.logger.info(f"Received connection request from peer at {address[0]}:{address[1]}. Sending handshake.")

        # formally establish and store connection
        connection =  PeerConnection(reader, writer, LogicCallbacks,self.peer_id)
        conn_details["connection"] = connection
        await connection.start()

        if self.verbose:
            self.logger.info(f"Received handshake from peer {connection.connected_peer_id} "
                             f"({address[0]}:{address[1]}).")

        conn_details["reader"] = reader
        conn_details["writer"] = writer

        conn_details["unchoked"] = False
        conn_details["preferred"] = False
        conn_details["download_rate"] = 0

        self.peer_info[connection.connected_peer_id] = conn_details
        self.num_connected_peers += 1

    # close the listening socket
    def close(self):
        if self.verbose:
            self.logger.info("Closing server...")
        self.listening_socket.close()
        if self.verbose:
            self.logger.info("Closed server.")

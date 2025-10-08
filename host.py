class Host:
    def __init__(self, name, ip_address, port_number, bitfield,
                 num_preferred_peers, unchoke_inteval, optimistic_unchoke_interval):
        self.name = name
        self.ip_address = ip_address
        self.port_number = port_number
        self.bitfield = bitfield  # array ?
        self.pieces_locations = dict({})  # pieces_location[piece_no] = file_location_on_disc

        self.num_preferred_peers = num_preferred_peers  # k, determined by config
        self.unchoke_interval = unchoke_inteval  # p, determined by config
        self.optimistic_unchoke_interval = optimistic_unchoke_interval  # m, determined by config

        self.connected_peers = dict({})  # connected_peers[peer ip:port_num] = (peer_num, peer_name, connection) ?
        self.preferred_peers = dict({})  # preferrred_peers[peer ip:port_num] = boolean (if peer preferred) ?
        self.unchoked_peers = dict({})  # unchoked_peers[peer ip:port_num] = boolean (if peer chocked) ?


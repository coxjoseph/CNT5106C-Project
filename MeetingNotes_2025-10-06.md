# Task Checklist

## Potential Class List
### Core 
- PeerNode
- PeerConnection
- NeighborState

### Messaging
- Handshake
- Message
    * Choke/Unchoke/Interested/NotInterested/Have/Bitfield/Request/Piece subclasses
- MessageType
- MessageCodec

### Pieces/Storage
- Bitfield
- PieceStore
- Piece

### Requesting
- RequestManager
- ChokingManager
- RateTracker

### Discovery
- PeerRegistry
- EventBus

### Misc
- Config
- ProtocolLogger

## Pipeline
1. `PeerNode` loads `Config` and `PieceStore` - listens and connects
2. `PeerConnection` performs `Handshake`, streams through `MessasgeCodec`, updates `NeighborState` and `PeerRegistry`
3. On receiving `Bitfield`/`Have`, `PeerNode` checks `Bitfield` - decides `Interested`/`NotInterested`
4. `ChokingManager` runs with `RateTracker` to choose neighbors and `Choke`/`Unchoke`
5. When unchoked `RequestManager` asks for a new index with `Request`
6. On `Piece` recv, `PieceStore` writes data and adjusts `Bitfield`. `PeerNode` broadcasts `Have` and starts next request


## Splitting Work
To me it makes sense to split into two separate but related areas - 
1. Networking and Protocol
- Implement `Handshake` to send/recv header
- Create `Message` and related classes `MessageType` and `MessageCodec`
- Implement send/recv loops, TCP, read/write, event dispatch

* Classes to implement (from the list above):
    1. Handshake
    2. Message
    3. MessageType
    4. Choke/Unchoke/Interested/NotInterested/Have/Bitfield/Request/Piece Msg
    5. MessageCodec
    6. PeerConnection
    7. ProtocolLogger

2. Logic and Choking
- Implement `NeighborState` and `PeerRegistry`
- Update bitfields as `have` or `bitfield` messages arrive
- Implement `PieceStore` and `Bitfield`, mark pieces as available or requested
- Implement `ChokingManager` with `p` and `m` timing
- Implement `RequestManager` to pick which pieces to request
- Handle responses and `have` messages

* Classes to implement (from the list above):
    1. PeerNode
    2. NeighborState
    3. Bitfield
    4. PieceStore
    5. Piece
    6. RequestManager
    7. ChokingManager
    8. RateTracker
    9. PeerRegistry
    10. EventBus
    11. Config

## API
To keep things separate, each part of the project should assume an API from the other with consistent signatures: 

An example one could be:
```python
# Logic Exposes
on_handshake(peer_id: int)
on_disconnect()
on_choke() / on_unchoke()
on_interested() / on_not_intereted()
on_have(index: int)
on_bitfield(bits: Bitfield)
on_request(index: int)
on_piece(index: int, data: bytes)

# Network Exposes
send_handshake(peer_id: int)
send_choke() / send_unchoke()
send_interested() / send_not_interested()
send_have(index: int)
send_bitfield(bits: Bitfield)
send_request(index: int)
send_piece(index: int, data: bytes)
close()
```

**We should consider making this using `typing.Protocol` and agreeing on it within a few days so we can develop**

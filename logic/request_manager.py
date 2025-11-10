import random
from typing import Dict, Optional, Set
from .bitfield import Bitfield


class RequestManager:
    """
    Enforces: one outstanding request per neighbor, no duplicate in-flight piece
    across neighbors. Random piece selection (per spec).
    """

    def __init__(self, total_pieces: int):
        self.total = total_pieces
        self.inflight_piece_by_peer: Dict[int, int] = {}  # peer_id -> piece
        self.inflight_peer_by_piece: Dict[int, int] = {}  # piece -> peer_id
        self.completed: Set[int] = set()

    def choose_for_neighbor(self, peer_id: int, neighbor_bits: Bitfield, local_bits: Bitfield) -> Optional[int]:
        # Don't assign if this neighbor already has an outstanding request
        if peer_id in self.inflight_piece_by_peer:
            return None
        candidates = [i for i in range(self.total)
                      if not local_bits.get(i)
                      and neighbor_bits.get(i)
                      and i not in self.inflight_peer_by_piece]
        if not candidates:
            return None
        return random.choice(candidates)

    def mark_inflight(self, peer_id: int, index: int) -> None:
        self.inflight_piece_by_peer[peer_id] = index
        self.inflight_peer_by_piece[index] = peer_id

    def clear_inflight_for_peer(self, peer_id: int) -> None:
        idx = self.inflight_piece_by_peer.pop(peer_id, None)
        if idx is not None:
            self.inflight_peer_by_piece.pop(idx, None)

    def complete(self, index: int) -> None:
        peer = self.inflight_peer_by_piece.pop(index, None)
        if peer is not None:
            self.inflight_piece_by_peer.pop(peer, None)
        self.completed.add(index)

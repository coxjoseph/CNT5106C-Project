import random
from typing import Dict, List

class RateTracker:
    """Track bytes downloaded from each neighbor in the last interval."""
    def __init__(self):
        self._bytes: Dict[int, int] = {}

    def add_download(self, peer_id: int, nbytes: int) -> None:
        self._bytes[peer_id] = self._bytes.get(peer_id, 0) + nbytes

    def snapshot_and_reset(self) -> Dict[int, int]:
        snap = dict(self._bytes)
        self._bytes.clear()
        return snap

class ChokingManager:
    def __init__(self, k_preferred: int):
        self.k = k_preferred
        self.rates = RateTracker()

    def select_preferred(self, interested_peer_ids: List[int], have_complete_file: bool) -> List[int]:
        if not interested_peer_ids:
            return []
        if have_complete_file:
            random.shuffle(interested_peer_ids)
            return interested_peer_ids[: self.k]

        snap = self.rates.snapshot_and_reset()
        ordered = sorted(interested_peer_ids, key=lambda pid: snap.get(pid, 0), reverse=True)
        # break ties randomly among peers with equal rate
        i = 0
        while i < len(ordered):
            j = i + 1
            while j < len(ordered) and snap.get(ordered[j], 0) == snap.get(ordered[i], 0):
                j += 1
            random.shuffle(ordered[i:j])
            i = j
        return ordered[: self.k]

    def pick_optimistic(self, choked_interested_ids: List[int]) -> int | None:
        return random.choice(choked_interested_ids) if choked_interested_ids else None

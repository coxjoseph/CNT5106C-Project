from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Iterable


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class TextEventLogger:
    """
    Writes required spec lines to logs/log_peer_<id>.log
    """

    def __init__(self, self_id: int, log_dir: str | Path = "logs"):
        self.self_id = int(self_id)
        self.log_path = Path(log_dir) / f"log_peer_{self.self_id}.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _w(self, line: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(f"{_ts()} {line}\n")

    # connection events

    def makes_connection_to(self, remote_id: int) -> None:
        self._w(f"Peer [{self.self_id}] makes a connection to Peer [{remote_id}].")

    def connected_from(self, remote_id: int) -> None:
        self._w(f"Peer [{self.self_id}] is connected from Peer [{remote_id}].")

    # neighbor set changes
    def preferred_neighbors(self, peer_ids: Iterable[int]) -> None:
        ids = ", ".join(str(p) for p in peer_ids) if peer_ids else ""
        self._w(f"Peer [{self.self_id}] has the preferred neighbors [{ids}].")

    def optimistic_neighbor(self, remote_id: int) -> None:
        self._w(f"Peer [{self.self_id}] has the optimistically unchoked neighbor [{remote_id}].")

    # choke/unchoke delivered to us
    def unchoked_by(self, remote_id: int) -> None:
        self._w(f"Peer [{self.self_id}] is unchoked by Peer [{remote_id}].")

    def choked_by(self, remote_id: int) -> None:
        self._w(f"Peer [{self.self_id}] is choked by Peer [{remote_id}].")

    # control msgs we received
    def received_have(self, remote_id: int, piece_idx: int) -> None:
        self._w(
            f"Peer [{self.self_id}] received the 'have' message from Peer [{remote_id}] for the piece [{piece_idx}].")

    def received_interested(self, remote_id: int) -> None:
        self._w(f"Peer [{self.self_id}] received the 'interested' message from Peer [{remote_id}].")

    def received_not_interested(self, remote_id: int) -> None:
        self._w(f"Peer [{self.self_id}] received the 'not interested' message from Peer [{remote_id}].")

    # piece progress
    def downloaded_piece_from(self, remote_id: int, piece_idx: int, have_count: int) -> None:
        self._w(f"Peer [{self.self_id}] has downloaded the piece [{piece_idx}] from Peer [{remote_id}]. "
                f"Now the number of pieces it has is [{have_count}].")

    def downloaded_complete_file(self) -> None:
        self._w(f"Peer [{self.self_id}] has downloaded the complete file.")

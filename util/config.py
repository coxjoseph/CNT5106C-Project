from dataclasses import dataclass
from pathlib import Path
from math import ceil


@dataclass
class CommonConfig:
    num_preferred_neighbors: int
    unchoking_interval: int
    optimistic_unchoking_interval: int
    file_name: str
    file_size: int
    piece_size: int

    @property
    def total_pieces(self) -> int:
        return ceil(self.file_size / self.piece_size)

    @property
    def last_piece_size(self) -> int:
        rem = self.file_size % self.piece_size
        return rem if rem != 0 else self.piece_size

    @classmethod
    def from_file(cls, path: str | Path) -> 'CommonConfig':
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f'Common.cfg not found: {path.resolve()}')
        config: dict[str, str] = {}

        for raw in path.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 2:
                raise ValueError(f'Malformed Common.cfg line: {raw}')
            key = parts[0]
            val = ' '.join(parts[1:]).strip()
            config[key] = val

        try:
            return cls(
                num_preferred_neighbors=int(config['NumberOfPreferredNeighbors']),
                unchoking_interval=int(config['UnchokingInterval']),
                optimistic_unchoking_interval=int(config['OptimisticUnchokingInterval']),
                file_name=config['FileName'],
                file_size=int(config['FileSize']),
                piece_size=int(config['PieceSize']),
            )
        except KeyError as e:
            raise ValueError(f'Common.cfg missing key: {e}') from e


@dataclass
class PeerRow:
    peer_id: int
    host: str
    port: int
    has_file: int


class PeerInfoTable:
    def __init__(self, rows: list[PeerRow]):
        self.rows = rows
        self.by_id = {r.peer_id: r for r in rows}
        self.ordered_ids = [r.peer_id for r in rows]

    @classmethod
    def from_file(cls, path: str | Path):
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f'PeerInfo.cfg not found: {path.resolve()}')
        rows: list[PeerRow] = []
        for raw in path.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) != 4:
                raise ValueError(f'Malformed PeerInfo.cfg line: {raw}')
            pid, host, port, has_file = parts
            rows.append(PeerRow(int(pid), host, int(port), int(has_file)))
        if not rows:
            raise ValueError('PeerInfo.cfg has no peers')
        return cls(rows)

    def get(self, peer_id: int) -> PeerRow:
        return self.by_id[peer_id]

    def earlier_peers(self, peer_id: int) -> list[PeerRow]:
        idx = self.ordered_ids.index(peer_id)
        return [self.by_id[i] for i in self.ordered_ids[:idx]]

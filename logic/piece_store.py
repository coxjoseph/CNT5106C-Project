import os
from .bitfield import Bitfield
from pathlib import Path


class PieceStore:

    def __init__(self, total_pieces: int, piece_size: int, last_piece_size: int,
                 data_dir: str, start_full: bool = False):
        os.makedirs(data_dir, exist_ok=True)
        self.total = total_pieces
        self.piece_size = piece_size
        self.last_piece_size = last_piece_size
        self.dir = data_dir
        self._bits = Bitfield.full(total_pieces) if start_full else Bitfield.empty(total_pieces)

    def bitfield(self) -> Bitfield:
        return self._bits

    def have(self, index: int) -> bool:
        return self._bits.get(index)

    def expected_size(self, index: int) -> int:
        return self.last_piece_size if index == self.total - 1 else self.piece_size

    def write_piece(self, index: int, data: bytes) -> bool:
        if index < 0 or index >= self.total:
            return False
        exp = self.expected_size(index)
        if len(data) != exp: 
            return False
        path = os.path.join(self.dir, f'piece_{index:06d}.bin')
        with open(path, 'wb') as f:
            f.write(data)
        self._bits.set(index, True)
        return True

    def read_piece(self, index: int) -> bytes:
        path = os.path.join(self.dir, f'piece_{index:06d}.bin')
        with open(path, 'rb') as f:
            return f.read()

    def reconstruct_full_file(self, file_name: str) -> Path:
        if self._bits.count() != self.total:
            raise RuntimeError('Cannot reconstruct full file - full file not present')

        out_path = Path(self.dir).parent / file_name
        with out_path.open('wb') as out:
            for i in range(self.total):
                size = self.last_piece_size if i == self.total - 1 else self.piece_size
                piece_path = Path(os.path.join(Path(self.dir), f'piece_{i:06d}.bin'))
                data = piece_path.read_bytes()
                if len(data) != size:
                    raise RuntimeError(f'Piece {piece_path} has unexpected size (got {len(data)}, expected {size})')
                out.write(data)
        return out_path

    def cleanup_pieces(self) -> None:
        for i in range(self.total):
            p = Path(os.path.join(self.dir, f'piece_{i:06d}.bin'))
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        try:
            os.rmdir(self.dir)
        except FileNotFoundError:
            pass

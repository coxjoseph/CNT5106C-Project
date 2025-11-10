class Bitfield:
    def __init__(self, total_pieces: int, bits: bytes | None = None):
        self.n = int(total_pieces)
        n_bytes = (self.n + 7) // 8
        self._b = bytearray(bits if bits is not None else b"\x00" * n_bytes)
        if len(self._b) != n_bytes:
            raise ValueError("bitfield length mismatch")

    @classmethod
    def empty(cls, total_pieces: int) -> "Bitfield":
        return cls(total_pieces)

    @classmethod
    def full(cls, total_pieces: int) -> "Bitfield":
        bf = cls(total_pieces)
        for i in range(total_pieces):
            bf.set(i, True)
        return bf

    @classmethod
    def from_bytes(cls, total_pieces: int, b: bytes) -> "Bitfield":
        return cls(total_pieces, b)

    def to_bytes(self) -> bytes:
        return bytes(self._b)

    def get(self, idx: int) -> bool:
        if not (0 <= idx < self.n):
            return False
        byte = idx // 8
        off = idx % 8
        return bool(self._b[byte] & (1 << (7 - off)))

    def set(self, idx: int, val: bool) -> None:
        if not (0 <= idx < self.n):
            return
        byte = idx // 8
        off = idx % 8
        mask = (1 << (7 - off))
        if val:
            self._b[byte] |= mask
        else:
            self._b[byte] &= ~mask

    def count(self) -> int:
        return sum(bin(b).count("1") for b in self._b)

    def missing_from(self, other: "Bitfield") -> list[int]:
        out = []
        for i in range(self.n):
            if not self.get(i) and other.get(i):
                out.append(i)
        return out

    # In case we need to print these:
    def __str__(self) -> str:
        bits = ''.join(f'{b:08b}' for b in self._b)
        return bits[:self.n]

    def summary(self) -> str:
        have = self.count()
        return f'{have}/{self.n} pieces'

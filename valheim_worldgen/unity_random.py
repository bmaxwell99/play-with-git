"""
Reimplementation of Unity's Random PRNG (xorshift128).

Ported from RyanDMcAfee/ValheimBakaLoader.
"""

import ctypes


class UnityRandom:
    def __init__(self, seed: int):
        self._x = 0
        self._y = 0
        self._z = 0
        self._w = 0
        self.init_state(seed)

    def init_state(self, seed: int) -> None:
        self._x = ctypes.c_uint32(seed).value
        self._y = ctypes.c_uint32(self._x * 1812433253 + 1).value
        self._z = ctypes.c_uint32(self._y * 1812433253 + 1).value
        self._w = ctypes.c_uint32(self._z * 1812433253 + 1).value

    def _next_uint(self) -> int:
        t = ctypes.c_uint32(self._x ^ (self._x << 11)).value
        t = ctypes.c_uint32(t ^ (t >> 8)).value
        self._x = self._y
        self._y = self._z
        self._z = self._w
        self._w = ctypes.c_uint32(self._w ^ (self._w >> 19) ^ t).value
        return self._w

    def _next_float01(self) -> float:
        return (self._next_uint() & 0x7FFFFF) / 8388607.0

    def range_float(self, min_val: float, max_val: float) -> float:
        """Unity Random.Range(float, float) — reversed lerp, both ends inclusive."""
        return (min_val - max_val) * self._next_float01() + max_val

    def range_int(self, min_val: int, max_val_exclusive: int) -> int:
        """Unity Random.Range(int, int) — min inclusive, max exclusive."""
        if min_val > max_val_exclusive:
            min_val, max_val_exclusive = max_val_exclusive, min_val
        diff = max_val_exclusive - min_val
        if diff == 0:
            return min_val
        return min_val + int(self._next_uint() % diff)

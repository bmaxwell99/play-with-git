"""
Valheim seed string to integer conversion.

Reimplements the game's GetStableHashCode used to turn a text seed
into the numeric seed that drives the PRNG.
"""

import ctypes


def seed_to_int(seed_str: str) -> int:
    """Convert a Valheim seed string to its integer hash, matching the game exactly."""
    if seed_str == "":
        return 0

    num = 5381
    num2 = num
    i = 0
    while i < len(seed_str) and ord(seed_str[i]) != 0:
        num = ctypes.c_int32(((num << 5) + num) ^ ord(seed_str[i])).value
        if i == len(seed_str) - 1 or ord(seed_str[i + 1]) == 0:
            break
        num2 = ctypes.c_int32(((num2 << 5) + num2) ^ ord(seed_str[i + 1])).value
        i += 2

    return ctypes.c_int32(num + ctypes.c_int32(num2 * 1566083941).value).value

"""
Valheim world generation algorithm.

Deterministic reimplementation of biome assignment, base height, per-biome
terrain height, and river/stream placement. Matches the game's output when
given the same seed.

Ported from RyanDMcAfee/ValheimBakaLoader (WorldGen.cs) and
BjarkeCK/ValheimSeedFinder (ValheimSeedFinder.cs).
"""

import math
from enum import IntFlag
from typing import Optional

from .perlin import noise as perlin_noise
from .unity_random import UnityRandom
from .fastnoise import FastNoise

WORLD_RADIUS = 10000.0
WORLD_EDGE = 10500.0
HEIGHT_MULTIPLIER = 200.0
SEA_LEVEL_METERS = 30.0
ASHLANDS_MIN_DISTANCE = 12000.0
ASHLANDS_Y_OFFSET = -4000.0


class Biome(IntFlag):
    NONE = 0
    MEADOWS = 1
    SWAMP = 2
    MOUNTAIN = 4
    BLACK_FOREST = 8
    PLAINS = 16
    ASH_LANDS = 32
    DEEP_NORTH = 64
    OCEAN = 256
    MISTLANDS = 512


BIOME_COLORS = {
    Biome.NONE: (0, 0, 0),
    Biome.MEADOWS: (145, 166, 92),
    Biome.SWAMP: (163, 112, 87),
    Biome.MOUNTAIN: (204, 204, 204),
    Biome.BLACK_FOREST: (51, 94, 59),
    Biome.PLAINS: (199, 199, 48),
    Biome.ASH_LANDS: (180, 40, 40),
    Biome.DEEP_NORTH: (240, 240, 255),
    Biome.OCEAN: (0, 0, 153),
    Biome.MISTLANDS: (82, 82, 82),
}


_noise_gen = None


def _get_noise_gen() -> FastNoise:
    global _noise_gen
    if _noise_gen is None:
        _noise_gen = FastNoise(0)
        _noise_gen.set_fractal_octaves(2)
        _noise_gen.set_seed(0)
    return _noise_gen


def _length(x: float, y: float) -> float:
    return math.sqrt(x * x + y * y)


def _clamp01(v: float) -> float:
    if v > 1.0:
        return 1.0
    if v < 0.0:
        return 0.0
    return v


def _lerp(a: float, b: float, t: float) -> float:
    if t <= 0.0:
        return a
    if t >= 1.0:
        return b
    return a * (1.0 - t) + b * t


def _lerp_step(l: float, h: float, v: float) -> float:
    return _clamp01((v - l) / (h - l))


def _smooth_step(mn: float, mx: float, x: float) -> float:
    n = _clamp01((x - mn) / (mx - mn))
    return n * n * (3.0 - 2.0 * n)


def _mathf_smooth_step(frm: float, to: float, t: float) -> float:
    t = _clamp01(t)
    t = -2.0 * t * t * t + 3.0 * t * t
    return float(to * t + frm * (1.0 - t))


def _remap(value, in_low, in_high, out_low, out_high):
    t = _clamp01((value - in_low) / (in_high - in_low))
    return _lerp(out_low, out_high, t)


def _blend_overlay(a, b):
    if a < 0.5:
        return 2.0 * a * b
    return 1.0 - 2.0 * (1.0 - a) * (1.0 - b)


def _fbm(px, py, octaves, lacunarity, gain):
    total = 0.0
    amp = 1.0
    x, y = float(px), float(py)
    for _ in range(octaves):
        total += amp * perlin_noise(x, y)
        amp *= gain
        x *= lacunarity
        y *= lacunarity
    return total


def _mathf_clamp(value, mn, mx):
    if value < mn:
        return mn
    if value > mx:
        return mx
    return value


def world_angle(wx: float, wy: float) -> float:
    return math.sin(math.atan2(wx, wy) * 20.0)


def is_ashlands(x: float, y: float) -> bool:
    angle = world_angle(x, y) * 100.0
    return _length(x, y + ASHLANDS_Y_OFFSET) > ASHLANDS_MIN_DISTANCE + angle


def is_deep_north(x: float, y: float) -> bool:
    angle = world_angle(x, y) * 100.0
    return _length(x, y + 4000.0) > 12000.0 + angle


class WorldGenerator:
    def __init__(self, seed: int, world_gen_version: int = 2):
        self._seed = seed
        self._version = world_gen_version

        self._min_mountain_distance = 1000.0
        self._min_darkland_noise = 0.4
        self._max_marsh_distance = 6000.0

        self._version_setup(world_gen_version)

        rng = UnityRandom(seed)
        self._offset0 = rng.range_float(-10000.0, 10000.0)
        self._offset1 = rng.range_float(-10000.0, 10000.0)
        self._offset2 = rng.range_float(-10000.0, 10000.0)
        self._offset3 = rng.range_float(-10000.0, 10000.0)
        self._river_seed = rng.range_int(-2147483648, 2147483647)
        self._stream_seed = rng.range_int(-2147483648, 2147483647)
        self._offset4 = rng.range_float(-10000.0, 10000.0)

        self._rng = rng

        self._river_points: dict[tuple[int, int], list[tuple[float, float, float, float]]] = {}
        self._lakes: list[tuple[float, float]] = []

        self._pregenerate()

    def _version_setup(self, version: int) -> None:
        if version <= 0:
            self._min_mountain_distance = 1500.0
        if version <= 1:
            self._min_darkland_noise = 0.5
            self._max_marsh_distance = 8000.0

    @property
    def seed(self) -> int:
        return self._seed

    # ------------------------------------------------------------------
    # Pregeneration: lakes, rivers, streams
    # ------------------------------------------------------------------

    def _pregenerate(self) -> None:
        self._find_lakes()
        self._place_rivers()
        self._place_streams(is_deep_north=False)
        self._place_streams(is_deep_north=True)

    def _find_lakes(self) -> None:
        candidates = []
        wy = -10000.0
        while wy <= 10000.0:
            wx = -10000.0
            while wx <= 10000.0:
                if _length(wx, wy) <= 10000.0 and self.get_base_height(wx, wy) < 0.05:
                    candidates.append((wx, wy))
                wx += 128.0
            wy += 128.0
        self._lakes = self._merge_points(candidates, 800.0)

    @staticmethod
    def _merge_points(points: list, rng: float) -> list:
        points = list(points)
        merged = []
        while points:
            cx, cy = points.pop(0)
            while points:
                best_idx = -1
                best_dist = 99999.0
                for i, (px, py) in enumerate(points):
                    if px == cx and py == cy:
                        continue
                    d = _length(cx - px, cy - py)
                    if d < rng and d < best_dist:
                        best_idx = i
                        best_dist = d
                if best_idx == -1:
                    break
                px, py = points[best_idx]
                cx = (cx + px) * 0.5
                cy = (cy + py) * 0.5
                points[best_idx] = points[-1]
                points.pop()
            merged.append((cx, cy))
        return merged

    def _place_rivers(self) -> None:
        self._rng.init_state(self._river_seed)
        rivers = []
        open_list = list(self._lakes)
        while len(open_list) > 1:
            lx, ly = open_list[0]
            end = self._find_random_river_end(rivers, self._lakes, (lx, ly), 2000.0, 0.4, 128.0)
            if end == -1 and not self._have_river_from(rivers, (lx, ly)):
                end = self._find_random_river_end(rivers, self._lakes, (lx, ly), 5000.0, 0.4, 128.0)
            if end != -1:
                p1 = self._lakes[end]
                width_max = self._rng.range_float(60.0, 100.0)
                width_min = self._rng.range_float(60.0, width_max)
                dist = _length(lx - p1[0], ly - p1[1])
                rivers.append({
                    "p0": (lx, ly),
                    "p1": p1,
                    "center": ((lx + p1[0]) * 0.5, (ly + p1[1]) * 0.5),
                    "width_max": width_max,
                    "width_min": width_min,
                    "curve_width": dist / 15.0,
                    "curve_wavelength": dist / 20.0,
                })
            else:
                open_list.pop(0)
        self._render_rivers(rivers)

    def _find_random_river_end(self, rivers, points, p, max_dist, height_limit, check_step):
        candidates = []
        for i, pt in enumerate(points):
            if pt[0] == p[0] and pt[1] == p[1]:
                continue
            if _length(p[0] - pt[0], p[1] - pt[1]) >= max_dist:
                continue
            if self._have_river_between(rivers, p, pt):
                continue
            if not self._is_river_allowed(p, pt, check_step, height_limit):
                continue
            candidates.append(i)
        if not candidates:
            return -1
        return candidates[self._rng.range_int(0, len(candidates))]

    @staticmethod
    def _have_river_from(rivers, p):
        for r in rivers:
            if r["p0"] == p or r["p1"] == p:
                return True
        return False

    @staticmethod
    def _have_river_between(rivers, p0, p1):
        for r in rivers:
            if (r["p0"] == p0 and r["p1"] == p1) or (r["p0"] == p1 and r["p1"] == p0):
                return True
        return False

    def _is_river_allowed(self, p0, p1, step, height_limit):
        dist = _length(p0[0] - p1[0], p0[1] - p1[1])
        dx = (p1[0] - p0[0]) / dist
        dy = (p1[1] - p0[1]) / dist
        all_water = True
        t = step
        while t <= dist - step:
            sx = p0[0] + dx * t
            sy = p0[1] + dy * t
            bh = self.get_base_height(sx, sy)
            if bh > height_limit:
                return False
            if bh > 0.05:
                all_water = False
            t += step
        return not all_water

    def _place_streams(self, is_deep_north: bool) -> None:
        self._rng.init_state(self._stream_seed)
        streams = []
        for _ in range(3000):
            start = self._find_stream_start(100, 26.0, 31.0, not is_deep_north)
            if start is None:
                continue
            end = self._find_stream_end(100, 36.0, 44.0, start, 80.0, 200.0, not is_deep_north)
            if end is None:
                continue
            cx = (start[0] + end[0]) * 0.5
            cy = (start[1] + end[1]) * 0.5
            mid_h = self._get_pregeneration_height(cx, cy, not is_deep_north)
            if mid_h < 26.0 or mid_h > 44.0:
                continue
            dist = _length(start[0] - end[0], start[1] - end[1])
            streams.append({
                "p0": start,
                "p1": end,
                "center": (cx, cy),
                "width_max": 20.0,
                "width_min": 20.0,
                "curve_width": dist / 15.0,
                "curve_wavelength": dist / 20.0,
            })
        add_rule = "skip_dn" if not is_deep_north else "only_dn"
        self._render_rivers(streams, add_rule)

    def _find_stream_start(self, iterations, min_h, max_h, river_pre_gen):
        for _ in range(iterations):
            wx = self._rng.range_float(-10000.0, 10000.0)
            wy = self._rng.range_float(-10000.0, 10000.0)
            h = self._get_pregeneration_height(wx, wy, river_pre_gen)
            if min_h < h < max_h:
                return (wx, wy)
        return None

    def _find_stream_end(self, iterations, min_h, max_h, start, min_len, max_len, river_pre_gen):
        shrink = (max_len - min_len) / iterations
        radius = max_len
        for _ in range(iterations):
            radius -= shrink
            angle = self._rng.range_float(0.0, math.pi * 2.0)
            cx = start[0] + math.sin(angle) * radius
            cy = start[1] + math.cos(angle) * radius
            h = self._get_pregeneration_height(cx, cy, river_pre_gen)
            if min_h < h < max_h:
                return (cx, cy)
        return None

    def _render_rivers(self, rivers, add_rule="all") -> None:
        accumulated: dict[tuple[int, int], list] = {}
        for river in rivers:
            if add_rule != "all":
                dn = is_deep_north(river["p0"][0], river["p0"][1])
                if dn and add_rule == "skip_dn":
                    continue
                if not dn and add_rule == "only_dn":
                    continue

            step = river["width_min"] / 8.0
            p0 = river["p0"]
            p1 = river["p1"]
            dist = _length(p0[0] - p1[0], p0[1] - p1[1])
            if dist < 0.001:
                continue
            dx = (p1[0] - p0[0]) / dist
            dy = (p1[1] - p0[1]) / dist
            px_perp = -dy
            py_perp = dx

            t = 0.0
            while t <= dist:
                f = t / river["curve_wavelength"]
                wobble = math.sin(f) * math.sin(f * 0.6341199874877930) * math.sin(f * 0.3341200053691864) * river["curve_width"]
                r = self._rng.range_float(river["width_min"], river["width_max"])
                rx = p0[0] + dx * t + px_perp * wobble
                ry = p0[1] + dy * t + py_perp * wobble
                self._add_river_point(accumulated, rx, ry, r)
                t += step

        for key, pts in accumulated.items():
            if key in self._river_points:
                self._river_points[key].extend(pts)
            else:
                self._river_points[key] = pts

    def _add_river_point(self, points, px, py, r):
        cx = int(math.floor((px + 32.0) / 64.0))
        cy = int(math.floor((py + 32.0) / 64.0))
        span = int(math.ceil(r / 64.0))
        for gy in range(cy - span, cy + span + 1):
            for gx in range(cx - span, cx + span + 1):
                gcx = gx * 64.0
                gcy = gy * 64.0
                ddx = abs(px - gcx)
                ddy = abs(py - gcy)
                if ddx < r + 32.0 and ddy < r + 32.0:
                    key = (gx, gy)
                    rp = (px, py, r, r * r)
                    if key in points:
                        points[key].append(rp)
                    else:
                        points[key] = [rp]

    def _get_river_weight(self, wx, wy):
        gx = int(math.floor((wx + 32.0) / 64.0))
        gy = int(math.floor((wy + 32.0) / 64.0))
        key = (gx, gy)
        pts = self._river_points.get(key)
        if pts is None:
            return 0.0, 0.0
        weight = 0.0
        weighted_width_sum = 0.0
        weight_sum = 0.0
        for rpx, rpy, rw, rw2 in pts:
            dx = rpx - wx
            dy = rpy - wy
            d_sq = dx * dx + dy * dy
            if d_sq < rw2:
                d = math.sqrt(d_sq)
                q = 1.0 - d / rw
                if q > weight:
                    weight = q
                weighted_width_sum += rw * q
                weight_sum += q
        width = 0.0
        if weight_sum > 0.0:
            width = weighted_width_sum / weight_sum
        return weight, width

    def _add_rivers(self, wx, wy, h):
        weight, width = self._get_river_weight(wx, wy)
        if weight <= 0.0:
            return h
        t = _lerp_step(20.0, 60.0, width)
        bed1 = _lerp(0.14, 0.12, t)
        bed2 = _lerp(0.139, 0.128, t)
        if h > bed1:
            h = _lerp(h, bed1, weight)
        if h > bed2:
            t2 = _lerp_step(0.85, 1.0, weight)
            h = _lerp(h, bed2, t2)
        return h

    # ------------------------------------------------------------------
    # Biome determination
    # ------------------------------------------------------------------

    def get_biome(self, wx: float, wy: float) -> Biome:
        dist = _length(wx, wy)
        base_h = self.get_base_height(wx, wy)
        angle = world_angle(wx, wy) * 100.0

        if is_ashlands(wx, wy):
            return Biome.ASH_LANDS
        if base_h <= 0.02:
            return Biome.OCEAN
        if is_deep_north(wx, wy):
            return Biome.DEEP_NORTH
        if base_h > 0.4:
            return Biome.MOUNTAIN

        if (perlin_noise(float(self._offset0 + wx) * 0.001, float(self._offset0 + wy) * 0.001) > 0.6
                and dist > 2000.0 and dist < self._max_marsh_distance
                and base_h > 0.05 and base_h < 0.25):
            return Biome.SWAMP

        if (perlin_noise(float(self._offset4 + wx) * 0.001, float(self._offset4 + wy) * 0.001) > self._min_darkland_noise
                and dist > 6000.0 + angle and dist < 10000.0):
            return Biome.MISTLANDS

        if (perlin_noise(float(self._offset1 + wx) * 0.001, float(self._offset1 + wy) * 0.001) > 0.4
                and dist > 3000.0 + angle and dist < 8000.0):
            return Biome.PLAINS

        if (perlin_noise(float(self._offset2 + wx) * 0.001, float(self._offset2 + wy) * 0.001) > 0.4
                and dist > 600.0 + angle and dist < 6000.0):
            return Biome.BLACK_FOREST

        if dist > 5000.0 + angle:
            return Biome.BLACK_FOREST

        return Biome.MEADOWS

    # ------------------------------------------------------------------
    # Base height
    # ------------------------------------------------------------------

    def get_base_height(self, wx: float, wy: float) -> float:
        dist = _length(wx, wy)
        x = wx + 100000.0 + self._offset0
        y = wy + 100000.0 + self._offset1

        h = perlin_noise(x * 0.002 * 0.5, y * 0.002 * 0.5) * perlin_noise(x * 0.003 * 0.5, y * 0.003 * 0.5)
        h += perlin_noise(x * 0.002, y * 0.002) * perlin_noise(x * 0.003, y * 0.003) * h * 0.9
        h += perlin_noise(x * 0.005, y * 0.005) * perlin_noise(x * 0.01, y * 0.01) * 0.5 * h
        h -= 0.07

        n1 = perlin_noise(x * 0.002 * 0.25 + 0.123, y * 0.002 * 0.25 + 0.15123)
        n2 = perlin_noise(x * 0.002 * 0.25 + 0.321, y * 0.002 * 0.25 + 0.231)
        channel = abs(n1 - n2)
        carve = 1.0 - _lerp_step(0.02, 0.12, channel)
        carve *= _smooth_step(744.0, 1000.0, dist)
        h *= 1.0 - carve

        if dist > 10000.0:
            t = _lerp_step(10000.0, 10500.0, dist)
            h = _lerp(h, -0.2, t)
            edge_start = 10490.0
            if dist > edge_start:
                t2 = _clamp01((dist - edge_start) / (10500.0 - edge_start))
                h = _lerp(h, -2.0, t2)
            return h

        if dist < self._min_mountain_distance and h > 0.28:
            t3 = _clamp01((h - 0.28) / 0.1)
            h = _lerp(
                _lerp(0.28, 0.38, t3),
                h,
                _lerp_step(self._min_mountain_distance - 400.0, self._min_mountain_distance, dist),
            )

        return h

    # ------------------------------------------------------------------
    # Per-biome heights
    # ------------------------------------------------------------------

    def get_height(self, wx: float, wy: float) -> float:
        biome = self.get_biome(wx, wy)
        return self.get_biome_height(biome, wx, wy)

    def _get_pregeneration_height(self, wx, wy, river_pre_gen):
        biome = self.get_biome(wx, wy)
        return self.get_biome_height(biome, wx, wy, pre_generation=True, river_pre_dn=river_pre_gen)

    def get_biome_height(self, biome: Biome, wx: float, wy: float,
                         pre_generation: bool = False, river_pre_dn: bool = True) -> float:
        if pre_generation:
            mult = HEIGHT_MULTIPLIER
        else:
            mult = HEIGHT_MULTIPLIER * self._create_ashlands_gap(wx, wy) * self._create_deep_north_gap(wx, wy)

        if _length(wx, wy) > WORLD_EDGE:
            return -2.0 * HEIGHT_MULTIPLIER

        if biome == Biome.SWAMP:
            return self._get_marsh_height(wx, wy) * mult
        elif biome == Biome.DEEP_NORTH:
            if pre_generation:
                return self._get_deep_north_height_pregen(wx, wy, river_pre_dn) * mult
            return self._get_deep_north_height(wx, wy) * mult
        elif biome == Biome.MOUNTAIN:
            return self._get_snow_mountain_height(wx, wy) * mult
        elif biome == Biome.BLACK_FOREST:
            return self._get_forest_height(wx, wy) * mult
        elif biome == Biome.OCEAN:
            return self.get_base_height(wx, wy) * mult
        elif biome == Biome.ASH_LANDS:
            if pre_generation:
                return self._get_ashlands_height_pregen(wx, wy) * mult
            return self._get_ashlands_height(wx, wy) * mult
        elif biome == Biome.PLAINS:
            return self._get_plains_height(wx, wy) * mult
        elif biome == Biome.MEADOWS:
            return self._get_meadows_height(wx, wy) * mult
        elif biome == Biome.MISTLANDS:
            if pre_generation:
                return self._get_forest_height(wx, wy) * mult
            return self._get_mistlands_height(wx, wy) * mult
        return 0.0

    def _get_marsh_height(self, wx, wy):
        orig_x, orig_y = wx, wy
        h = 0.137
        wx += 100000.0
        wy += 100000.0
        bump = perlin_noise(wx * 0.04, wy * 0.04) * perlin_noise(wx * 0.08, wy * 0.08)
        h += bump * 0.03
        h = self._add_rivers(orig_x, orig_y, h)
        h += perlin_noise(wx * 0.1, wy * 0.1) * 0.01
        return h + perlin_noise(wx * 0.4, wy * 0.4) * 0.003

    def _get_meadows_height(self, wx, wy):
        orig_x, orig_y = wx, wy
        base_h = self.get_base_height(wx, wy)
        wx += 100000.0 + self._offset3
        wy += 100000.0 + self._offset3
        bump = perlin_noise(wx * 0.01, wy * 0.01) * perlin_noise(wx * 0.02, wy * 0.02)
        bump += perlin_noise(wx * 0.05, wy * 0.05) * perlin_noise(wx * 0.1, wy * 0.1) * bump * 0.5
        h = base_h + bump * 0.1
        above = h - 0.15
        k = _clamp01(base_h / 0.4)
        if above > 0.0:
            h -= above * (1.0 - k) * 0.75
        h = self._add_rivers(orig_x, orig_y, h)
        h += perlin_noise(wx * 0.1, wy * 0.1) * 0.01
        return h + perlin_noise(wx * 0.4, wy * 0.4) * 0.003

    def _get_forest_height(self, wx, wy):
        orig_x, orig_y = wx, wy
        h = self.get_base_height(wx, wy)
        wx += 100000.0 + self._offset3
        wy += 100000.0 + self._offset3
        bump = perlin_noise(wx * 0.01, wy * 0.01) * perlin_noise(wx * 0.02, wy * 0.02)
        bump += perlin_noise(wx * 0.05, wy * 0.05) * perlin_noise(wx * 0.1, wy * 0.1) * bump * 0.5
        h += bump * 0.1
        h = self._add_rivers(orig_x, orig_y, h)
        h += perlin_noise(wx * 0.1, wy * 0.1) * 0.01
        return h + perlin_noise(wx * 0.4, wy * 0.4) * 0.003

    def _get_mistlands_height(self, wx, wy):
        orig_x, orig_y = wx, wy
        h = self.get_base_height(wx, wy)
        wx += 100000.0 + self._offset3
        wy += 100000.0 + self._offset3
        ridges = perlin_noise(wx * 0.02 * 0.7, wy * 0.02 * 0.7) * perlin_noise(wx * 0.04 * 0.7, wy * 0.04 * 0.7)
        ridges += perlin_noise(wx * 0.03 * 0.7, wy * 0.03 * 0.7) * perlin_noise(wx * 0.05 * 0.7, wy * 0.05 * 0.7) * ridges * 0.5
        ridges = ridges ** 1.5 if ridges > 0 else ridges
        h += ridges * 0.4
        h = self._add_rivers(orig_x, orig_y, h)
        ridge_mask = _clamp01(ridges * 7.0)
        h += perlin_noise(wx * 0.1, wy * 0.1) * 0.03 * ridge_mask
        h += perlin_noise(wx * 0.4, wy * 0.4) * 0.01 * ridge_mask
        smooth = h + perlin_noise(wx * 0.4, wy * 0.4) * 0.002
        terraced = h
        terraced = math.ceil(terraced * 400.0) / 400.0
        return _lerp(smooth, terraced, ridge_mask)

    def _get_plains_height(self, wx, wy):
        orig_x, orig_y = wx, wy
        base_h = self.get_base_height(wx, wy)
        wx += 100000.0 + self._offset3
        wy += 100000.0 + self._offset3
        bump = perlin_noise(wx * 0.01, wy * 0.01) * perlin_noise(wx * 0.02, wy * 0.02)
        bump += perlin_noise(wx * 0.05, wy * 0.05) * perlin_noise(wx * 0.1, wy * 0.1) * bump * 0.5
        h = base_h + bump * 0.1
        above = h - 0.15
        k = _clamp01(base_h / 0.4)
        if above > 0.0:
            h -= above * (1.0 - k) * 0.75
        h = self._add_rivers(orig_x, orig_y, h)
        h += perlin_noise(wx * 0.1, wy * 0.1) * 0.01
        return h + perlin_noise(wx * 0.4, wy * 0.4) * 0.003

    def _get_snow_mountain_height(self, wx, wy):
        orig_x, orig_y = wx, wy
        h = self.get_base_height(wx, wy)
        tilt = self._base_height_tilt(wx, wy)
        wx += 100000.0 + self._offset3
        wy += 100000.0 + self._offset3
        above = h - 0.4
        h += above
        bump = perlin_noise(wx * 0.01, wy * 0.01) * perlin_noise(wx * 0.02, wy * 0.02)
        bump += perlin_noise(wx * 0.05, wy * 0.05) * perlin_noise(wx * 0.1, wy * 0.1) * bump * 0.5
        h += bump * 0.2
        h = self._add_rivers(orig_x, orig_y, h)
        h += perlin_noise(wx * 0.1, wy * 0.1) * 0.01
        h += perlin_noise(wx * 0.4, wy * 0.4) * 0.003
        return h + perlin_noise(wx * 0.2, wy * 0.2) * 2.0 * tilt

    def _base_height_tilt(self, wx, wy):
        left = self.get_base_height(wx - 1.0, wy)
        right = self.get_base_height(wx + 1.0, wy)
        down = self.get_base_height(wx, wy - 1.0)
        up = self.get_base_height(wx, wy + 1.0)
        return abs(right - left) + abs(down - up)

    def _get_deep_north_height_pregen(self, wx, wy, river_pregen):
        orig_x, orig_y = wx, wy
        h = self.get_base_height(wx, wy)
        if not river_pregen:
            h += 0.1
        wx += 100000.0 + self._offset3
        wy += 100000.0 + self._offset3
        above = max(0.0, h - 0.4)
        h += above
        bump = perlin_noise(wx * 0.01, wy * 0.01) * perlin_noise(wx * 0.02, wy * 0.02)
        bump += perlin_noise(wx * 0.05, wy * 0.05) * perlin_noise(wx * 0.1, wy * 0.1) * bump * 0.5
        h += bump * 0.2
        h *= 1.2
        h = self._add_rivers(orig_x, orig_y, h)
        h += perlin_noise(float(wx * 0.1), float(wy * 0.1)) * 0.01
        return h + perlin_noise(float(wx * 0.4), float(wy * 0.4)) * 0.003

    def _get_deep_north_height(self, wx, wy):
        orig_x, orig_y = wx, wy
        base_h = self.get_base_height(wx, wy) + 0.1
        wx += 100000.0 + self._offset3
        wy += 100000.0 + self._offset3
        bump = perlin_noise(wx * 0.01, wy * 0.01) * perlin_noise(wx * 0.02, wy * 0.02)
        bump += perlin_noise(wx * 0.05, wy * 0.05) * perlin_noise(wx * 0.1, wy * 0.1) * bump * 0.5
        h = base_h + bump * 0.1
        over = h - 0.15
        lift = _clamp01(base_h / 0.4)
        if over > 0.0:
            h -= over * (1.0 - lift) * 0.75
        h = self._add_rivers(orig_x, orig_y, h)
        h += perlin_noise(wx * 0.1, wy * 0.1) * 0.01
        return h + perlin_noise(wx * 0.4, wy * 0.4) * 0.003

    def _get_ashlands_height_pregen(self, wx, wy):
        orig_x, orig_y = wx, wy
        h = self.get_base_height(wx, wy)
        wx += 100000.0 + self._offset3
        wy += 100000.0 + self._offset3
        bump = perlin_noise(wx * 0.01, wy * 0.01) * perlin_noise(wx * 0.02, wy * 0.02)
        bump += perlin_noise(wx * 0.05, wy * 0.05) * perlin_noise(wx * 0.1, wy * 0.1) * bump * 0.5
        h += bump * 0.1
        h += 0.1
        h += perlin_noise(wx * 0.1, wy * 0.1) * 0.01
        h += perlin_noise(wx * 0.4, wy * 0.4) * 0.003
        return self._add_rivers(orig_x, orig_y, h)

    def _get_ashlands_height(self, wx, wy):
        ng = _get_noise_gen()
        x, y = float(wx), float(wy)
        base_h = self.get_base_height(x, y)

        angle = world_angle(x, y) * 100.0
        band = _length(x, y + ASHLANDS_Y_OFFSET - ASHLANDS_Y_OFFSET * 0.3) - (ASHLANDS_MIN_DISTANCE + angle)
        band = abs(band) / 1000.0
        band = 1.0 - _clamp01(band)
        band = _mathf_smooth_step(0.1, 1.0, band)
        ew_fade = 1.0 - _clamp01(abs(x) / 7500.0)
        band *= ew_fade

        outer = _length(x, y) - 10150.0
        outer = 1.0 - _clamp01(outer / 600.0)

        x += 100000.0 + self._offset3
        y += 100000.0 + self._offset3

        cells = 0.0
        cell_amp = 1.0
        cell_scale = 0.33000001311302185
        for _ in range(5):
            cells += cell_amp * _mathf_smooth_step(0.0, 1.0, ng.get_cellular(x * cell_scale, y * cell_scale))
            cell_scale *= 2.0
            cell_amp *= 0.5
        cells = _remap(cells, -1.0, 1.0, 0.0, 1.0)
        shaped = _lerp(band, _blend_overlay(band, cells), 0.5)

        h = _lerp(base_h, 0.15, 0.75)
        h += shaped * 0.5
        h = _lerp(-1.0, h, _mathf_smooth_step(0.0, 1.0, outer))

        lava_level = 0.15
        cracks = 0.0
        crack_amp = 1.0
        crack_scale = 8.0
        for _ in range(3):
            cracks += crack_amp * ng.get_cellular(x * crack_scale, y * crack_scale)
            crack_scale *= 2.0
            crack_amp *= 0.5
        cracks = _remap(cracks, -1.0, 1.0, 0.0, 1.0)
        cracks = _clamp01(cracks ** 4.0 * 2.0)

        simplex = ng.get_simplex_fractal(x * 0.075, y * 0.075)
        simplex = _remap(simplex, -1.0, 1.0, 0.0, 1.0)
        simplex = simplex ** 1.4
        h *= simplex

        crack_field = _fbm(float(x * 0.01), float(y * 0.01), 3, 2.0, 0.5)
        crack_field *= _clamp01(_remap(band, 0.0, 0.5, 0.5, 1.0))
        crack_field = _lerp_step(0.7, 1.0, crack_field)
        crack_field = crack_field ** 2.0

        crack_mask = _blend_overlay(crack_field, cracks)
        crack_mask *= _clamp01((h - lava_level - 0.02) / 0.01)

        depth = perlin_noise(x * 0.05 + 5124.0, y * 0.05 + 5000.0)
        depth = depth ** 2.0
        depth = _remap(depth, 0.0, 1.0, 0.01, 0.055)
        cut = _mathf_clamp(h - depth, lava_level + 0.01, 5000.0)
        h = _lerp(h, cut, crack_mask)

        return h

    @staticmethod
    def _create_ashlands_gap(wx, wy):
        angle = world_angle(wx, wy) * 100.0
        value = _length(wx, wy + ASHLANDS_Y_OFFSET) - (ASHLANDS_MIN_DISTANCE + angle)
        value = _clamp01(abs(value) / 400.0)
        return _mathf_smooth_step(0.0, 1.0, value)

    @staticmethod
    def _create_deep_north_gap(wx, wy):
        angle = world_angle(wx, wy) * 100.0
        value = _length(wx, wy + 4000.0) - (12000.0 + angle)
        value = _clamp01(abs(value) / 400.0)
        return _mathf_smooth_step(0.0, 1.0, value)

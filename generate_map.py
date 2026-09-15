#!/usr/bin/env python3
"""
Valheim Map Generator CLI

Generate biome and height maps from a Valheim world seed.

Usage:
    python generate_map.py <seed> [--size 512] [--height] [--output map.png]
"""

import argparse
import sys
import time

from valheim_worldgen.seed import seed_to_int
from valheim_worldgen.world_generator import WorldGenerator
from valheim_worldgen.renderer import render_biome_map, render_height_map


def main():
    parser = argparse.ArgumentParser(description="Generate a Valheim world map from a seed")
    parser.add_argument("seed", help="World seed string (e.g. 'HHcLC5acQt')")
    parser.add_argument("--size", type=int, default=512, help="Output image size in pixels (default: 512)")
    parser.add_argument("--height", action="store_true", help="Render height map instead of biome map")
    parser.add_argument("--height-shading", action="store_true", help="Apply height-based shading to biome map")
    parser.add_argument("--output", "-o", default=None, help="Output filename (default: map_<seed>.png)")
    parser.add_argument("--version", type=int, default=2, help="World generation version (default: 2)")
    args = parser.parse_args()

    seed_int = seed_to_int(args.seed)
    print(f"Seed: '{args.seed}' -> {seed_int}")

    print("Initializing world generator (lakes, rivers, streams)...")
    t0 = time.time()
    gen = WorldGenerator(seed_int, args.version)
    t1 = time.time()
    print(f"  Pregeneration done in {t1 - t0:.1f}s")
    print(f"  Lakes: {len(gen._lakes)}, River grid cells: {len(gen._river_points)}")

    output = args.output
    if output is None:
        suffix = "height" if args.height else "biome"
        output = f"map_{args.seed}_{suffix}.png"

    print(f"Rendering {args.size}x{args.size} {'height' if args.height else 'biome'} map...")
    t0 = time.time()
    if args.height:
        img = render_height_map(gen, args.size)
    else:
        img = render_biome_map(gen, args.size, show_height=args.height_shading)
    t1 = time.time()
    print(f"  Rendered in {t1 - t0:.1f}s")

    img.save(output)
    print(f"Saved to {output}")


if __name__ == "__main__":
    main()

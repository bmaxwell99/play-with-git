"""
Map renderer for Valheim world generation.

Produces a biome map image from a WorldGenerator instance.
"""

import math
from PIL import Image

from .world_generator import WorldGenerator, Biome, BIOME_COLORS, _length


SHALLOW_COLOR = (102, 102, 255)


def render_biome_map(gen: WorldGenerator, size: int = 512, show_height: bool = False) -> Image.Image:
    """Render a biome map as a PIL Image.

    Args:
        gen: Initialized WorldGenerator
        size: Output image width/height in pixels
        show_height: If True, modulate biome colors by terrain height
    """
    img = Image.new("RGB", (size, size))
    pixels = img.load()

    for py in range(size):
        wy = ((py / (size - 1.0)) * 2.0 - 1.0) * 10000.0
        for px in range(size):
            wx = ((px / (size - 1.0)) * 2.0 - 1.0) * 10000.0

            if _length(wx, wy) > 10500.0:
                pixels[px, py] = (10, 10, 30)
                continue

            biome = gen.get_biome(wx, wy)
            color = BIOME_COLORS.get(biome, (0, 0, 0))

            if show_height and biome != Biome.OCEAN:
                h = gen.get_biome_height(biome, wx, wy)
                if h < 30.0 and biome != Biome.OCEAN:
                    color = SHALLOW_COLOR
                else:
                    brightness = max(0.4, min(1.2, 0.6 + h / 200.0))
                    color = tuple(max(0, min(255, int(c * brightness))) for c in color)

            pixels[px, py] = color

    return img


def render_height_map(gen: WorldGenerator, size: int = 512) -> Image.Image:
    """Render a grayscale height map as a PIL Image."""
    img = Image.new("L", (size, size))
    pixels = img.load()

    for py in range(size):
        wy = ((py / (size - 1.0)) * 2.0 - 1.0) * 10000.0
        for px in range(size):
            wx = ((px / (size - 1.0)) * 2.0 - 1.0) * 10000.0

            if _length(wx, wy) > 10500.0:
                pixels[px, py] = 0
                continue

            h = gen.get_height(wx, wy)
            val = max(0, min(255, int((h + 50.0) / 400.0 * 255.0)))
            pixels[px, py] = val

    return img

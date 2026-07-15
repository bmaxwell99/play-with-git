#!/usr/bin/env python3
"""Project coordinate data onto a Palworld map as one shareable HTML file.

Takes a set of labelled points (base locations, spawn coords, fast-travel
statues, dig spots — anything with an x/y) and renders them over a map
image as a single self-contained HTML file: image embedded as a data URI,
markers coloured by category with hover tooltips, clickable layer toggles,
and a live world-coordinate readout as you move the mouse. Drop the file in
Slack/Discord or open it anywhere — no server, no dependencies.

The map's coordinate transform is CALIBRATED, not hardcoded: you give two
or three reference points (a world coord you know maps to a pixel on your
map image) and the tool solves the affine transform. This survives the 1.0
coordinate tweaks and works with any map image (extracted, wiki, or the
built-in grid).

    # 2 reference points -> axis-aligned fit (Palworld's usual case;
    # its map Y is flipped, which two refs capture automatically).
    # Use --ref=... (equals) so a leading negative coord isn't mistaken
    # for a flag:
    python3 plot_map.py points.csv --map worldmap.png --out map.html \
        --ref=123.4,-45.6,812,1440 --ref=-300,200,210,300

    # No map image -> clean coordinate grid (still fully usable):
    python3 plot_map.py points.csv --out map.html --autofit

points.csv columns: x,y,label[,category]  (category drives colour/layers)
or pass a pals.json-style file; see --help.

Stdlib only; no dependencies.
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import mimetypes
from pathlib import Path

# Categorical palette (colour-blind-safe-ish), assigned in first-seen order.
PALETTE = [
    "#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#b07aa1",
    "#edc948", "#76b7b2", "#ff9da7", "#9c755f", "#bab0ac",
]


def load_points(path: Path) -> list[dict]:
    """Read points from CSV (x,y,label[,category]) or JSON.

    JSON may be a list of {x,y,label,category} objects, or a pals.json
    from parse_pals.py (in which case each pal needs x/y added — we look
    for 'x'/'y' or 'lon'/'lat' keys and skip pals without coords).
    """
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        rows = data.get("pals", data) if isinstance(data, dict) else data
    else:
        rows = list(csv.DictReader(text.splitlines()))

    points = []
    for row in rows:
        x = row.get("x", row.get("X", row.get("lon")))
        y = row.get("y", row.get("Y", row.get("lat")))
        if x is None or y is None or x == "" or y == "":
            continue
        points.append({
            "x": float(x),
            "y": float(y),
            "label": str(row.get("label") or row.get("name") or row.get("id") or ""),
            "category": str(row.get("category") or row.get("work") or "point"),
        })
    if not points:
        raise SystemExit(f"error: no points with x/y found in {path}")
    return points


def parse_ref(spec: str) -> tuple[float, float, float, float]:
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) != 4:
        raise SystemExit(f"error: --ref must be wx,wy,px,py (got {spec!r})")
    return tuple(float(p) for p in parts)  # type: ignore[return-value]


def solve_affine(refs: list[tuple[float, float, float, float]]) -> list[float]:
    """Solve [a,b,c,d,e,f] so px=a*wx+b*wy+c, py=d*wx+e*wy+f.

    2 refs -> axis-aligned (b=d=0), solved independently per axis.
    3 refs -> full affine via a 3x3 linear solve (handles rotated maps).
    """
    if len(refs) == 2:
        (wx0, wy0, px0, py0), (wx1, wy1, px1, py1) = refs
        if wx0 == wx1 or wy0 == wy1:
            raise SystemExit("error: 2 reference points must differ in both world x and world y")
        a = (px1 - px0) / (wx1 - wx0)
        e = (py1 - py0) / (wy1 - wy0)
        return [a, 0.0, px0 - a * wx0, 0.0, e, py0 - e * wy0]
    if len(refs) >= 3:
        r = refs[:3]
        # Solve the x-equation and y-equation over the same [wx,wy,1] basis.
        basis = [[wx, wy, 1.0] for wx, wy, _, _ in r]
        abc = _solve3(basis, [px for _, _, px, _ in r])
        de_f = _solve3(basis, [py for _, _, _, py in r])
        return [abc[0], abc[1], abc[2], de_f[0], de_f[1], de_f[2]]
    raise SystemExit("error: need at least 2 --ref points to calibrate (or use --autofit)")


def _solve3(m: list[list[float]], rhs: list[float]) -> list[float]:
    """Gaussian elimination for a 3x3 system. Stdlib-only."""
    a = [row[:] + [rhs[i]] for i, row in enumerate(m)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise SystemExit("error: reference points are collinear; pick 3 non-collinear points")
        a[col], a[pivot] = a[pivot], a[col]
        piv = a[col][col]
        a[col] = [v / piv for v in a[col]]
        for r in range(3):
            if r != col:
                factor = a[r][col]
                a[r] = [v - factor * a[col][i] for i, v in enumerate(a[r])]
    return [a[0][3], a[1][3], a[2][3]]


def autofit_affine(points: list[dict], width: int, height: int, pad: int = 60) -> list[float]:
    """Fit all points into width x height with padding. Flips Y (screen down)."""
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    spanx = (maxx - minx) or 1.0
    spany = (maxy - miny) or 1.0
    a = (width - 2 * pad) / spanx
    e = -(height - 2 * pad) / spany  # negative: world +y -> screen up
    return [a, 0.0, pad - a * minx, 0.0, e, (height - pad) - e * miny]


def image_data_uri(path: Path) -> tuple[str, int, int]:
    """Return (data URI, width, height). Reads PNG/GIF/JPEG dims from header."""
    raw = path.read_bytes()
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    uri = f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
    w, h = _image_size(raw)
    return uri, w, h


def _image_size(raw: bytes) -> tuple[int, int]:
    """Minimal PNG/GIF/JPEG dimension sniffing (no PIL)."""
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return int.from_bytes(raw[6:8], "little"), int.from_bytes(raw[8:10], "little")
    if raw[:2] == b"\xff\xd8":  # JPEG: scan for SOF marker
        i = 2
        while i < len(raw) - 9:
            if raw[i] != 0xFF:
                i += 1
                continue
            marker = raw[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                return int.from_bytes(raw[i + 7:i + 9], "big"), int.from_bytes(raw[i + 5:i + 7], "big")
            i += 2 + int.from_bytes(raw[i + 2:i + 4], "big")
    raise SystemExit("error: could not read image dimensions; pass --width/--height explicitly")


def build_html(points, transform, bg, width, height, title):
    """Assemble the self-contained HTML. bg is a data-URI string or None."""
    cats, colour = [], {}
    for p in points:
        if p["category"] not in colour:
            colour[p["category"]] = PALETTE[len(cats) % len(PALETTE)]
            cats.append(p["category"])

    payload = {
        "points": [{**p, "color": colour[p["category"]]} for p in points],
        "transform": transform,
        "categories": [{"name": c, "color": colour[c]} for c in cats],
        "width": width, "height": height,
        "bg": bg,
        "title": title,
    }
    data_json = json.dumps(payload)
    safe_title = html.escape(title)

    # Single-file page: theme-aware, responsive, image (or grid) + markers.
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
  /* Token-based theming: slate neutrals biased toward the map's teal
     accent. prefers-color-scheme sets the default; the viewer's theme
     toggle stamps data-theme on :root and must win in both directions. */
  :root {{
    color-scheme: light dark;
    --bg: #eef1f3; --panel: #dfe4e8; --ink: #16202b; --muted: #5a6b78;
    --line: #c3ccd3; --tip-bg: #16202b; --tip-ink: #f2f5f7; --marker-ring: #ffffff;
    --accent: #2a7d8c;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0f1720; --panel: #1a2430; --ink: #dde5eb; --muted: #8a9aa8;
      --line: #2c3846; --tip-bg: #dde5eb; --tip-ink: #0f1720; --marker-ring: #0f1720;
      --accent: #4fb3c4;
    }}
  }}
  :root[data-theme="light"] {{
    --bg: #eef1f3; --panel: #dfe4e8; --ink: #16202b; --muted: #5a6b78;
    --line: #c3ccd3; --tip-bg: #16202b; --tip-ink: #f2f5f7; --marker-ring: #ffffff;
    --accent: #2a7d8c;
  }}
  :root[data-theme="dark"] {{
    --bg: #0f1720; --panel: #1a2430; --ink: #dde5eb; --muted: #8a9aa8;
    --line: #2c3846; --tip-bg: #dde5eb; --tip-ink: #0f1720; --marker-ring: #0f1720;
    --accent: #4fb3c4;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font: 14px/1.4 system-ui, sans-serif; background: var(--bg); color: var(--ink); }}
  header {{ padding: 12px 16px; border-bottom: 1px solid var(--line); }}
  h1 {{ font-size: 16px; margin: 0; text-wrap: balance; }}
  .wrap {{ display: flex; gap: 12px; padding: 12px; flex-wrap: wrap; align-items: flex-start; }}
  .stage {{ position: relative; overflow: auto; border: 1px solid var(--line);
            border-radius: 8px; background: var(--panel); max-width: 100%; }}
  .canvas {{ position: relative; }}
  .canvas img {{ display: block; }}
  .grid {{ position: absolute; inset: 0; color: var(--ink); }}
  .marker {{ position: absolute; width: 12px; height: 12px; margin: -6px 0 0 -6px;
             border-radius: 50%; border: 2px solid var(--marker-ring); cursor: pointer;
             box-shadow: 0 1px 3px rgba(0,0,0,.5); }}
  .marker:hover {{ transform: scale(1.5); z-index: 5; }}
  .marker:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
  .tip {{ position: fixed; pointer-events: none; background: var(--tip-bg); color: var(--tip-ink);
          padding: 4px 8px; border-radius: 6px; font-size: 12px; white-space: nowrap;
          opacity: 0; transition: opacity .1s; z-index: 20; }}
  aside {{ min-width: 180px; }}
  .legend label {{ display: flex; align-items: center; gap: 8px; padding: 3px 0; cursor: pointer; }}
  .swatch {{ width: 12px; height: 12px; border-radius: 3px; flex: none; }}
  .readout {{ margin-top: 12px; font-variant-numeric: tabular-nums; color: var(--muted); }}
  .readout b {{ color: var(--accent); font-weight: 600; }}
  .hint {{ color: var(--muted); font-size: 12px; margin-top: 8px; max-width: 30ch; }}
</style>
</head>
<body>
<header><h1>{safe_title}</h1></header>
<div class="wrap">
  <div class="stage"><div class="canvas" id="canvas"></div></div>
  <aside>
    <div class="legend" id="legend"></div>
    <div class="readout" id="readout">world: <b>—, —</b></div>
    <div class="hint">Hover a marker for its label. Toggle categories in the legend.
      Coordinates are the calibrated world x/y.</div>
  </aside>
</div>
<div class="tip" id="tip"></div>
<script>
const D = {data_json};
const [a,b,c,d,e,f] = D.transform;
const det = a*e - b*d;
// inverse affine for the live mouse readout
function toWorld(px,py) {{
  const ix = px - c, iy = py - f;
  return [ (e*ix - b*iy)/det, (-d*ix + a*iy)/det ];
}}
const canvas = document.getElementById('canvas');
canvas.style.width = D.width + 'px';
canvas.style.height = D.height + 'px';
if (D.bg) {{
  const img = document.createElement('img');
  img.src = D.bg; img.width = D.width; img.height = D.height; img.alt = '';
  canvas.appendChild(img);
}} else {{
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('class','grid');
  svg.setAttribute('width', D.width); svg.setAttribute('height', D.height);
  const step = 100;
  for (let gx=0; gx<=D.width; gx+=step) add(gx,0,gx,D.height);
  for (let gy=0; gy<=D.height; gy+=step) add(0,gy,D.width,gy);
  function add(x1,y1,x2,y2) {{
    const l = document.createElementNS(NS,'line');
    l.setAttribute('x1',x1); l.setAttribute('y1',y1);
    l.setAttribute('x2',x2); l.setAttribute('y2',y2);
    l.setAttribute('stroke','currentColor'); l.setAttribute('stroke-width','0.5');
    l.setAttribute('opacity','0.18'); svg.appendChild(l);
  }}
  canvas.appendChild(svg);
}}
const tip = document.getElementById('tip');
const byCat = {{}};
for (const p of D.points) {{
  const px = a*p.x + b*p.y + c, py = d*p.x + e*p.y + f;
  const m = document.createElement('div');
  m.className = 'marker'; m.style.left = px+'px'; m.style.top = py+'px';
  m.style.background = p.color;
  m.dataset.cat = p.category;
  m.addEventListener('mousemove', ev => {{
    tip.textContent = `${{p.label || p.category}}  (${{p.x.toFixed(1)}}, ${{p.y.toFixed(1)}})`;
    tip.style.left = (ev.clientX+12)+'px'; tip.style.top = (ev.clientY+12)+'px';
    tip.style.opacity = 1;
  }});
  m.addEventListener('mouseleave', () => tip.style.opacity = 0);
  (byCat[p.category] ||= []).push(m);
  canvas.appendChild(m);
}}
const legend = document.getElementById('legend');
for (const cat of D.categories) {{
  const lab = document.createElement('label');
  const cb = document.createElement('input');
  cb.type='checkbox'; cb.checked=true;
  cb.onchange = () => (byCat[cat.name]||[]).forEach(m => m.style.display = cb.checked?'':'none');
  const sw = document.createElement('span'); sw.className='swatch'; sw.style.background=cat.color;
  lab.append(cb, sw, document.createTextNode(cat.name));
  legend.appendChild(lab);
}}
const readout = document.getElementById('readout');
canvas.addEventListener('mousemove', ev => {{
  const r = canvas.getBoundingClientRect();
  const [wx,wy] = toWorld(ev.clientX - r.left, ev.clientY - r.top);
  readout.innerHTML = `world: <b>${{wx.toFixed(1)}}, ${{wy.toFixed(1)}}</b>`;
}});
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("points", type=Path, help="CSV (x,y,label[,category]) or JSON of points")
    parser.add_argument("--map", type=Path, help="background map image (PNG/JPEG/GIF); omit for a grid")
    parser.add_argument("--out", type=Path, default=Path("map.html"))
    parser.add_argument("--ref", action="append", default=[], metavar="wx,wy,px,py",
                        help="calibration point: world x,y -> pixel x,y (give 2 or 3). "
                             "Use the equals form (--ref=-300,200,210,300) so a leading "
                             "negative coordinate isn't parsed as a flag.")
    parser.add_argument("--autofit", action="store_true",
                        help="ignore --ref and fit all points into the canvas (good for grid mode)")
    parser.add_argument("--width", type=int, help="canvas width (default: image width, or 1000 for grid)")
    parser.add_argument("--height", type=int, help="canvas height (default: image height, or 1000 for grid)")
    parser.add_argument("--title", default="Palworld map")
    parser.add_argument("--serve", nargs="?", type=int, const=8000, default=None, metavar="PORT",
                        help="after writing, serve the map on http://localhost:PORT (default 8000)")
    args = parser.parse_args()

    points = load_points(args.points)

    bg = None
    if args.map:
        bg, iw, ih = image_data_uri(args.map)
        width, height = args.width or iw, args.height or ih
    else:
        width, height = args.width or 1000, args.height or 1000

    if args.ref and not args.autofit:
        transform = solve_affine([parse_ref(r) for r in args.ref])
    else:
        transform = autofit_affine(points, width, height)

    if args.out.parent != Path(""):
        args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_html(points, transform, bg, width, height, args.title), encoding="utf-8")
    print(f"wrote {args.out}  ({len(points)} points, "
          f"{'image' if bg else 'grid'} background, {width}x{height})")

    if args.serve is not None:
        serve(args.out, args.serve)


def serve(out: Path, port: int) -> None:
    """Serve the map's directory on localhost so the HTML is viewable in a browser."""
    import functools
    import http.server
    import socketserver

    directory = out.resolve().parent
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    url = f"http://localhost:{port}/{out.name}"
    try:
        with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
            print(f"serving map at {url}  (Ctrl+C to stop)")
            httpd.serve_forever()
    except OSError as exc:
        raise SystemExit(f"error: could not bind port {port} ({exc}); try --serve <other-port>")
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()

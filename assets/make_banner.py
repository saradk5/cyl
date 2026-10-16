"""Regenerate the README banner from the ART and LOGO data in cyl.py.

Writes a transparent SVG per theme, and a transparent PNG too when Pillow is
installed - all four from the same list of shapes, so they cannot drift apart.

There is no background plate: the banner sits straight on the page, so it reads
seamlessly in a README. That costs one thing - a transparent image cannot carry
a near-black tagline onto a dark page - so the tagline and its rule are the only
colours that flip, and each theme gets its own file:

    assets/cyl.svg       assets/cyl.png        for light backgrounds
    assets/cyl-dark.svg  assets/cyl-dark.png   for dark ones

The README hands each reader the right one with <picture media="...">.

    python3 assets/make_banner.py
"""
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cyl", HERE.parent / "cyl.py")
cyl = importlib.util.module_from_spec(spec)
sys.argv = ["cyl"]
spec.loader.exec_module(cyl)

CW, CH = 12, 24                  # one terminal cell
PX_H = CH // 2                   # a half-block pixel is half a cell tall
PAD, GAP, SO = 12, 26, 6         # padding, cap-to-wordmark gap, shadow offset
FONT_SIZE = 19

# Brand ink, the same in both themes. Gold carries on white and on near-black
# alike; the cap's pale band is enclosed by ember on both sides, so its shape
# survives either background even where the fill itself is low-contrast. The
# tassel cord ("D") is a lone 1px line, so it takes ember rather than cream.
INK = {"G": "#d9a441", "E": "#8a5f22", "C": "#efe7d8", "D": "#8a5f22", "K": "#bf5b48"}
FACE, SHADOW = "#d9a441", "#8a5f22"
TEXT = "complete your lessons"

# Only the tagline and its rule have to flip; everything above is brand colour.
THEMES = {"": {"tagline": "#2b2721", "rule": "#c9c1b2"},
          "-dark": {"tagline": "#ded5c6", "rule": "#4a443b"}}

art_w = len(cyl.ART[0]) * CW
block_h = len(cyl.ART) * PX_H
cells = [(r, c) for r, line in enumerate(cyl.LOGO)
         for c, ch in enumerate(line) if ch == "█"]
r0, r1 = min(r for r, _ in cells), max(r for r, _ in cells)
lx = PAD + art_w + GAP
W = lx + (max(c for _, c in cells) + 1) * CW + SO + PAD
H = PAD + block_h + 54 + PAD
ty = PAD + block_h + 34


def build(theme):
    """("rect", x, y, w, h, fill) | ("text", x, y, fill, s) for one theme."""
    shapes = []

    def rect(x, y, w, h, fill):
        shapes.append(("rect", x, y, w, h, fill))

    # --- the mortarboard: merge runs of one colour into a single rect ---
    for row, line in enumerate(cyl.ART):
        col = 0
        while col < len(line):
            ch, run = line[col], 0
            while col + run < len(line) and line[col + run] == ch:
                run += 1
            if ch in INK:
                rect(PAD + col * CW, PAD + row * PX_H, run * CW, PX_H, INK[ch])
            col += run

    # --- the wordmark: solid faces plus a real offset drop shadow, which is
    # --- what the figlet font's box-drawing glyphs were imitating in the terminal
    oy = PAD + (block_h - ((r1 - r0 + 1) * CH + SO)) / 2 - r0 * CH
    for dx, dy, fill in ((SO, SO, SHADOW), (0, 0, FACE)):
        for row in range(r0, r1 + 1):
            cols = sorted(c for r, c in cells if r == row)
            for c in cols:
                if c - 1 in cols:
                    continue
                n = 1
                while c + n in cols:
                    n += 1
                rect(lx + c * CW + dx, oy + row * CH + dy, n * CW, CH, fill)

    shapes.append(("text", PAD, ty, THEMES[theme]["tagline"], TEXT))
    rect(PAD, ty + 14, 300, 1.5, THEMES[theme]["rule"])
    return shapes


def write_svg(dest, shapes):
    mono = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" role="img" aria-label="cyl - {TEXT}">',
           f'<title>cyl - {TEXT}</title>',
           '<g shape-rendering="crispEdges">']
    for shape in shapes:
        if shape[0] == "rect":
            _, x, y, w, h, fill = shape
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>')
        else:
            _, x, y, fill, text = shape
            out.append(f'</g><text x="{x}" y="{y}" font-family="{mono}" '
                       f'font-size="{FONT_SIZE}" fill="{fill}">{text}</text>'
                       '<g shape-rendering="crispEdges">')
    out += ['</g>', '</svg>']
    dest.write_text("\n".join(out) + "\n")
    return dest.stat().st_size


def write_png(dest, shapes, scale=2):
    """Same shapes at 2x on a transparent canvas. Skipped without Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    img = Image.new("RGBA", (W * scale, H * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = None
    for path in ("/System/Library/Fonts/Menlo.ttc",
                 "/System/Library/Fonts/SFNSMono.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        if pathlib.Path(path).exists():
            font = ImageFont.truetype(path, FONT_SIZE * scale)
            break
    for shape in shapes:
        if shape[0] == "rect":
            _, x, y, w, h, fill = shape
            draw.rectangle([x * scale, y * scale,
                            (x + w) * scale - 1, (y + h) * scale - 1], fill=fill)
        elif font:
            _, x, y, fill, text = shape
            draw.text((x * scale, y * scale), text, font=font, fill=fill, anchor="ls")
    img.save(dest, optimize=True)
    return dest.stat().st_size


for theme in THEMES:
    shapes = build(theme)
    svg = write_svg(HERE / f"cyl{theme}.svg", shapes)
    print(f"wrote cyl{theme}.svg  {W}x{H}  {svg} bytes")
    png = write_png(HERE / f"cyl{theme}.png", shapes)
    print(f"wrote cyl{theme}.png  {W*2}x{H*2}  {png} bytes" if png
          else f"skipped cyl{theme}.png (Pillow not installed)")

"""Erzeugt packaging/icon.png (1024 px) für EXE und Mac-App.

Das Icon wird beim Build gezeichnet, damit im Repo nur Textdateien liegen.
PyInstaller wandelt die PNG-Datei automatisch in .ico (Windows) bzw.
.icns (macOS) um – dafür muss Pillow installiert sein.

Aufruf:  python packaging/make_icon.py
"""

import os

from PIL import Image, ImageDraw

SIZE = 1024
BG = (20, 23, 28, 255)        # --bg-panel
ACCENT = (53, 208, 186, 255)  # --accent
GRID = (38, 43, 51, 255)      # --border

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")


def main():
    scale = 4  # erst groß zeichnen, dann glätten
    s = SIZE * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # abgerundetes Quadrat mit Lattice-Raster
    margin = int(s * 0.04)
    d.rounded_rectangle((margin, margin, s - margin, s - margin), radius=int(s * 0.2), fill=BG)
    step = int(s * 0.09)
    for x in range(margin + step, s - margin, step):
        d.line((x, margin * 3, x, s - margin * 3), fill=GRID, width=scale * 3)
        d.line((margin * 3, x, s - margin * 3, x), fill=GRID, width=scale * 3)

    # T-Shirt-Umriss
    u = s / 64.0
    shirt = [(24, 13), (12, 20), (17, 30), (22, 27), (22, 52), (42, 52), (42, 27),
             (47, 30), (52, 20), (40, 13), (36, 16.5), (28, 16.5)]
    pts = [(x * u, y * u) for x, y in shirt]
    d.polygon(pts, fill=(53, 208, 186, 40))
    d.line(pts + [pts[0]], fill=ACCENT, width=int(u * 2.6), joint="curve")

    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    img.save(OUT)
    print("Icon geschrieben:", OUT)


if __name__ == "__main__":
    main()

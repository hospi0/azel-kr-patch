# -*- coding: utf-8 -*-
"""FNT 전체 글리프를 격자 시트 PNG로 뽑는다."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image
from iso9660 import Iso
import fnt

if __name__ == '__main__':
    track, name, outpng = sys.argv[1:4]
    cols = int(sys.argv[4]) if len(sys.argv) > 4 else 32
    first = int(sys.argv[5], 0) if len(sys.argv) > 5 else 0
    count = int(sys.argv[6], 0) if len(sys.argv) > 6 else 10 ** 9

    iso = Iso(track)
    d = {p: (l, s) for p, l, s in iso.walk()}
    l, s = d[name]
    glyphs = fnt.parse(iso.read(l, s))[first:first + count]
    rowsn = (len(glyphs) + cols - 1) // cols
    cell, scale = 17, 2
    img = Image.new('L', (cols * cell, rowsn * cell), 40)
    px = img.load()
    for i, g in enumerate(glyphs):
        ox, oy = (i % cols) * cell, (i // cols) * cell
        for r, v in enumerate(fnt.rows(g)):
            for c in range(16):
                px[ox + c, oy + r] = 255 if (v >> (15 - c)) & 1 else 0
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(outpng)
    print('%s: %d 글리프 → %s' % (name, len(glyphs), outpng))

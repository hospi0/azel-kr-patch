# -*- coding: utf-8 -*-
"""FNT 글리프를 «사람이 읽을 수 있는» 시트 PNG 로 뽑는다.

  python tools/fnt_sheet.py <FNT> <출력접두> [행수] [배율]
    예: python tools/fnt_sheet.py work/uniq/EVTZOAH.FNT work/sheet/zoah

16열 × ROWS 행씩 여러 장으로 나눈다. 각 칸 왼쪽 위에 인덱스를 적지 않는다 —
글리프만 깔끔히 보여야 판독이 정확하다. 인덱스는 시트 순번 × 칸수로 계산한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image
import fnt as fntmod

COLS = 16


def main():
    path, prefix = sys.argv[1], sys.argv[2]
    rows = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    scale = int(sys.argv[4]) if len(sys.argv) > 4 else 4

    glyphs = fntmod.parse(open(path, 'rb').read())
    os.makedirs(os.path.dirname(prefix) or '.', exist_ok=True)
    per = COLS * rows
    cell = 17
    n = 0
    for start in range(0, len(glyphs), per):
        part = glyphs[start:start + per]
        r = (len(part) + COLS - 1) // COLS
        img = Image.new('L', (COLS * cell, r * cell), 60)
        px = img.load()
        for i, g in enumerate(part):
            ox, oy = (i % COLS) * cell, (i // COLS) * cell
            for y, v in enumerate(fntmod.rows(g)):
                for x in range(16):
                    px[ox + x, oy + y] = 255 if (v >> (15 - x)) & 1 else 0
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        out = '%s_%02d.png' % (prefix, n)
        img.save(out)
        print('%s  글리프 %d..%d' % (out, start, start + len(part) - 1))
        n += 1
    print('총 %d글리프, 시트 %d장' % (len(glyphs), n))


if __name__ == '__main__':
    main()

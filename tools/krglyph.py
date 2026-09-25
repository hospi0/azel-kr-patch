# -*- coding: utf-8 -*-
"""한글 글리프를 Azel `.FNT` 포맷(32 B = 16행 × BE16)으로 굽는다.

  python tools/krglyph.py <문자열> <출력.png> [--font Galmuri11] [--dx 2] [--dy 1]

원본 실측:
  * 셀 16×16, 잉크 박스 x 2..13 / y 1..11  → **실사용 12×11**
  * 갈무리11 의 한글 잉크는 11×11 이라 그대로 들어간다.

★픽셀 폰트는 BDF 직독 — TTF 를 «디자인 px 가 아닌 크기»로 그리면 획이 탈락한다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bdf

FONTDIR = r'C:/claude/project/conker-kr-patch/my folder/Galmuri-v2.40.3'
CELL = 16
INK_X, INK_Y = 2, 1          # 원본 잉크 박스 좌상단


def load(name='Galmuri11'):
    return bdf.Bdf(os.path.join(FONTDIR, name + '.bdf'))


REF = '가힣긴뷁종물의래씨제'      # 원점 기준으로 삼을 한글 표본


def origin(font):
    """폰트의 «한글 잉크 박스 좌상단» — 전 글자가 공유하는 고정 원점.

    ⛔글자마다 «자기 잉크의 최상단»으로 정규화하면 안 된다. 한글은 잉크가 셀을
      꽉 채워 티가 안 나지만, **아래쪽에만 잉크가 있는 글자가 위로 끌려 올라간다** —
      실기에서 쉼표가 어퍼스트로피처럼 위에 찍혔다(「하지만'힘은」).
      마침표·`」`·`（）`도 같은 병이다. 원점은 **폰트 전체에 하나**여야 한다.
    """
    xs, ys = [], []
    for ch in REF:
        b = font.bits(ch)
        if b:
            xs += [p[0] for p in b]
            ys += [p[1] for p in b]
    return (min(xs), min(ys)) if xs else (0, 0)


_ORIGIN = {}


def glyph(font, ch, dx=INK_X, dy=INK_Y):
    """글자 → 32바이트 FNT 글리프. 없으면 None."""
    bits = font.bits(ch)
    if bits is None:
        return None
    if not bits:
        return b'\x00' * 32
    key = id(font)
    if key not in _ORIGIN:
        _ORIGIN[key] = origin(font)
    ox, oy = _ORIGIN[key]
    rows = [0] * CELL
    for x, y in bits:
        px, py = x - ox + dx, y - oy + dy
        if 0 <= px < CELL and 0 <= py < CELL:
            rows[py] |= 1 << (15 - px)
    return b''.join(struct.pack('>H', r) for r in rows)


def main():
    text = sys.argv[1]
    out = sys.argv[2]
    name = 'Galmuri11'
    dx, dy = INK_X, INK_Y
    for i, a in enumerate(sys.argv):
        if a == '--font':
            name = sys.argv[i + 1]
        elif a == '--dx':
            dx = int(sys.argv[i + 1])
        elif a == '--dy':
            dy = int(sys.argv[i + 1])
    font = load(name)
    from PIL import Image
    miss = [c for c in text if font.bits(c) is None]
    cells = [glyph(font, c, dx, dy) for c in text if font.bits(c) is not None]
    cols = min(16, len(cells)) or 1
    rows_n = (len(cells) + cols - 1) // cols
    img = Image.new('L', (cols * 17, rows_n * 17), 60)
    px = img.load()
    for i, g in enumerate(cells):
        ox, oy = (i % cols) * 17, (i // cols) * 17
        for r in range(16):
            v = struct.unpack_from('>H', g, r * 2)[0]
            for c in range(16):
                px[ox + c, oy + r] = 255 if (v >> (15 - c)) & 1 else 0
    img.resize((img.width * 5, img.height * 5), Image.NEAREST).save(out)
    print('%s: %d글자 → %s (폰트 %s, 원점 +%d+%d)' % (out, len(cells), out, name, dx, dy))
    if miss:
        print('★없는 글자:', ''.join(miss))


if __name__ == '__main__':
    main()

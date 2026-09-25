# -*- coding: utf-8 -*-
"""Azel `.FNT` — 16x16 1bpp 글리프 서브셋 폰트.

관측(디스크1 전 65개 파일에서 (size-18)==count*32 위반 0건):
    +0x00  BE16  글리프 수
    +0x02  BE16  0x0004  (의미 미확정)
    +0x04  14B   0x00 패딩
    +0x12  글리프 배열, 1개당 32B = 16행 x BE16(왼쪽 픽셀이 MSB)
"""
import struct

HDR = 18
GLYPH = 32


def parse(data):
    n = struct.unpack_from('>H', data, 0)[0]
    assert HDR + n * GLYPH == len(data), '글리프 수 %d 와 파일 크기 %d 불일치' % (n, len(data))
    return [data[HDR + i * GLYPH: HDR + (i + 1) * GLYPH] for i in range(n)]


def rows(glyph):
    """글리프 → 16개의 16비트 행 값."""
    return [struct.unpack_from('>H', glyph, r * 2)[0] for r in range(16)]


def ink_box(glyphs):
    """글리프 집합의 실제 잉크 범위 (x0, y0, x1, y1) — 셀 크기를 추측하지 않고 실측한다."""
    x0, y0, x1, y1 = 16, 16, -1, -1
    for g in glyphs:
        for r, v in enumerate(rows(g)):
            if not v:
                continue
            y0 = min(y0, r)
            y1 = max(y1, r)
            for c in range(16):
                if (v >> (15 - c)) & 1:
                    x0 = min(x0, c)
                    x1 = max(x1, c)
    return x0, y0, x1, y1

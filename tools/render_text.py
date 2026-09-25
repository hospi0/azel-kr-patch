# -*- coding: utf-8 -*-
"""PRG 안의 글리프 인덱스 스트림을 짝 FNT로 렌더해 PNG로 뽑는다.

토큰 모델(가설, 이 스크립트가 검증 도구):
    byte >= 0x80 : 2바이트 글자 토큰, index = ((b & 0x7F) << 8) | next
    byte <  0x80 : 1바이트 제어코드  (관측: 0x06 = 개행, 0x00 = 종료)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image
from iso9660 import Iso
import fnt


def decode(data, off, nglyph, limit=4096, stop_at_zero=True):
    """off부터 토큰 시퀀스를 읽는다 → [('g',idx) | ('c',code)], 끝 오프셋."""
    out = []
    i = off
    end = min(len(data), off + limit)
    while i < end:
        b = data[i]
        if b >= 0x80:
            if i + 1 >= end:
                break
            idx = ((b & 0x7F) << 8) | data[i + 1]
            if idx >= nglyph:
                break
            out.append(('g', idx))
            i += 2
        else:
            out.append(('c', b))
            i += 1
            if b == 0x00 and stop_at_zero:
                break
    return out, i


def render(tokens, glyphs, scale=2, pad=2):
    lines = [[]]
    for kind, v in tokens:
        if kind == 'g':
            lines[-1].append(v)
        elif v in (0x06, 0x00):
            lines.append([])
    lines = [l for l in lines if l] or [[]]
    w = max(len(l) for l in lines) * 16
    h = len(lines) * 16
    img = Image.new('L', (w, h), 0)
    px = img.load()
    for ly, line in enumerate(lines):
        for lx, idx in enumerate(line):
            for r, val in enumerate(fnt.rows(glyphs[idx])):
                for c in range(16):
                    if (val >> (15 - c)) & 1:
                        px[lx * 16 + c, ly * 16 + r] = 255
    img = img.resize((w * scale, h * scale), Image.NEAREST)
    out = Image.new('L', (img.width + pad * 2, img.height + pad * 2), 0)
    out.paste(img, (pad, pad))
    return out


if __name__ == '__main__':
    track, prg, fntname, off, outpng = sys.argv[1:6]
    iso = Iso(track)
    d = {p: (l, s) for p, l, s in iso.walk()}
    l, s = d[prg]
    data = iso.read(l, s)
    l, s = d[fntname]
    glyphs = fnt.parse(iso.read(l, s))
    print('%s: 글리프 %d개, 잉크 박스 %s' % (fntname, len(glyphs), fnt.ink_box(glyphs)))
    limit = int(sys.argv[6], 0) if len(sys.argv) > 6 else 4096
    toks, end = decode(data, int(off, 0), len(glyphs), limit, stop_at_zero=False)
    ng = sum(1 for k, _ in toks if k == 'g')
    ctrl = sorted({v for k, v in toks if k == 'c'})
    print('0x%X → 0x%X : 글자 %d개, 제어코드 %s' % (int(off, 0), end, ng, [hex(c) for c in ctrl]))
    render(toks, glyphs).save(outpng)
    print('저장:', outpng)

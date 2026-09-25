# -*- coding: utf-8 -*-
"""PRG 문자열 테이블을 사람이 읽는 형태로 덤프한다.

  python tools/dump_text.py <PRG> <FNT|-> <start_off> [count]

JP는 기본 폰트(index 0..255)를 basemap 표로 유니코드화하고,
장면 FNT 글리프(256~)는 `【n】` 자리표시자로 남긴다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import fnt as fntmod
import fntmap
import strtab

SCENE = None      # 장면 FNT 판독표 (data/fnt/<이름>.txt)


def render(toks, raw=b''):
    # 파일명 문자열만 진짜 ASCII다 — 글리프로 렌더하면 깨져 보인다.
    if strtab.is_asset_name(raw):
        return raw.decode('ascii')
    s = []
    for k, v in toks:
        if k in ('g', 'g1'):
            if v >= 256 and SCENE and v - 256 < len(SCENE):
                s.append(SCENE[v - 256])
            else:
                s.append(basemap.ch(v))
        elif k == 'c':
            s.append('\\n' if v == 0x06 else '<%02X>' % v)
        else:
            s.append('<!%02X>' % v)
    return ''.join(s)


def main():
    global SCENE
    prg, fntpath, start = sys.argv[1], sys.argv[2], int(sys.argv[3], 0)
    count = int(sys.argv[4]) if len(sys.argv) > 4 else 10 ** 9
    data = open(prg, 'rb').read()
    nmax = 0x8000
    if fntpath != '-':
        nglyph = len(fntmod.parse(open(fntpath, 'rb').read()))
        nmax = 256 + nglyph
        name = os.path.basename(fntpath).rsplit('.', 1)[0]
        ok, ln = fntmap.check(name, nglyph)
        if ok is False:
            print('# ★판독표 길이 불일치: %s 표 %d vs 글리프 %d — 쓰지 않는다'
                  % (name, ln, nglyph))
        elif ok:
            SCENE = fntmap.load(name)
    tab, end = strtab.parse_table(data, start, nmax, lenient=True)
    print('# %s  start=0x%X end=0x%X  strings=%d  nmax=%d'
          % (os.path.basename(prg), start, end, len(tab), nmax))
    for n, (off, raw, toks) in enumerate(tab[:count]):
        print('%4d %06X %-6s %s' % (n, off, strtab.kind(raw, toks), render(toks, raw)))


if __name__ == '__main__':
    main()

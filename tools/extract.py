# -*- coding: utf-8 -*-
"""디스크에서 파일을 골라 work/ 아래로 뽑는다.

  python tools/extract.py <track1.bin> <outdir> [이름 ...]
이름을 안 주면 텍스트·폰트 관련 확장자(PRG/FNT/DAT/TXT)를 전부 뽑는다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from iso9660 import Iso

TEXTY = ('.PRG', '.FNT', '.DAT', '.TXT')


def main():
    track, outdir = sys.argv[1:3]
    names = sys.argv[3:]
    iso = Iso(track)
    ents = {p.lstrip('/'): (l, s) for p, l, s in iso.walk() if not p.endswith('/')}
    if not names:
        names = [n for n in ents if n.upper().endswith(TEXTY)]
    os.makedirs(outdir, exist_ok=True)
    tot = 0
    for n in names:
        key = n.lstrip('/')
        if key not in ents:
            print('없음:', n)
            continue
        l, s = ents[key]
        with open(os.path.join(outdir, os.path.basename(key)), 'wb') as f:
            f.write(iso.read(l, s))
        tot += s
    print('%d개 %d B → %s' % (len(names), tot, outdir))


if __name__ == '__main__':
    main()

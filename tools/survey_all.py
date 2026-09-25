# -*- coding: utf-8 -*-
"""디스크 4장 **전수** — 확장자를 정해 놓지 않고 텍스트가 든 파일을 찾는다.

  python tools/survey_all.py

★확장자를 열거해서 훑으면 «없는 줄 알았던» 텍스트를 통째로 놓친다.
  세션2의 「디스크 2~4 조사 완료」가 `.PRG`·`.FNT`·`.DAT` 만 본 것이라
  `.EPK` 를 17개나 놓쳤다. 여기서는 **모든 파일**을 같은 잣대로 본다.

잣대 = 「널종단 글리프 인덱스 스트림이 여러 개 몰려 있는가」.
글리프 index 는 기본폰트 0~255 + 그 파일의 장면 폰트뿐이므로,
**index 상한을 넘는 것이 섞이면 글자가 아니다**(이 제약이 잡음을 크게 줄인다).
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import strtab
from iso9660 import Iso

ROOT = r'F:\hospi\roms\ss roms\azel'
DISCS = [
    ('D1', r'Azel - Panzer Dragoon RPG (Japan) (Disc 1) (2M)\Azel - Panzer Dragoon RPG (Japan) (Disc 1) (2M) (Track 1).bin'),
    ('D2', r'Azel - Panzer Dragoon RPG (Japan) (Disc 2) (2M)\Azel - Panzer Dragoon RPG (Japan) (Disc 2) (2M) (Track 1).bin'),
    ('D3', r'Azel - Panzer Dragoon RPG (Japan) (Disc 3) (2M)\Azel - Panzer Dragoon RPG (Japan) (Disc 3) (2M) (Track 1).bin'),
    ('D4', r'Azel - Panzer Dragoon RPG (Japan) (Disc 4) (2M, 3M)\Azel - Panzer Dragoon RPG (Japan) (Disc 4) (2M, 3M) (Track 1).bin'),
]

RUN = re.compile(rb'(?:[\x80-\x8f].){3,}\x00')
KANA = {i for i in range(256) if '぀' <= basemap.ch(i) <= 'ヿ'}
PUNCT = {i for i in range(256) if basemap.ch(i) in '、。「」『』！？…（）・ー'}
NMAX = 256 + 1024                 # 어떤 장면 폰트도 이보다 크지 않다


def hits(data):
    out = 0
    chars = 0
    for m in RUN.finditer(data):
        tab, _ = strtab.parse_table(data, m.start(), NMAX, lenient=False)
        if not tab:
            continue
        o, raw, t = tab[0]
        g = [v for k, v in t if k in ('g', 'g1')]
        if len(g) < 4:
            continue
        base = [v for v in g if v < 256]
        kana = sum(1 for v in base if v in KANA or v in PUNCT)
        if not base or kana < len(base) * 0.6 or kana < 3:
            continue
        if strtab.is_asset_name(raw):
            continue
        out += 1
        chars += len(g)
    return out, chars


def main():
    for tag, rel in DISCS:
        iso = Iso(os.path.join(ROOT, rel))
        rows = []
        for name, lba, size in iso.walk():
            if name.endswith('/') or size == 0 or size > 60 * 1024 * 1024:
                continue
            ext = name.rsplit('.', 1)[-1].upper() if '.' in name else ''
            if ext in ('PCM', 'CPK'):        # 음성·영상은 건너뛴다
                continue
            data = iso.read(lba, size)
            n, c = hits(data)
            if n >= 3:
                rows.append((n, c, name, size, ext))
        rows.sort(reverse=True)
        print('=== %s : 텍스트가 든 파일 %d개' % (tag, len(rows)))
        byext = collections.Counter()
        for n, c, name, size, ext in rows:
            byext[ext] += 1
        print('    확장자별:', dict(byext.most_common()))
        for n, c, name, size, ext in rows[:60]:
            print('    %-22s %9dB  문자열 %5d / 글자 %6d' % (name, size, n, c))
        sys.stdout.flush()


if __name__ == '__main__':
    main()

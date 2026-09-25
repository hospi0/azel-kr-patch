# -*- coding: utf-8 -*-
"""디스크 4장의 «파일 목록»을 확장자별로 세고, 디스크1에 없는 것을 짚는다.

  python tools/disc_survey.py

★세션2의 「디스크 2~4 조사 완료」는 **PRG·FNT·DAT 만** 본 것이라
  `.EPK` 같은 종류는 애초에 대상 밖이었다. 확장자를 정해 놓고 훑으면
  «없는 줄 알았던» 텍스트를 통째로 놓친다.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from iso9660 import Iso

ROOT = r'F:\hospi\roms\ss roms\azel'
DISCS = [
    ('D1', r'Azel - Panzer Dragoon RPG (Japan) (Disc 1) (2M)\Azel - Panzer Dragoon RPG (Japan) (Disc 1) (2M) (Track 1).bin'),
    ('D2', r'Azel - Panzer Dragoon RPG (Japan) (Disc 2) (2M)\Azel - Panzer Dragoon RPG (Japan) (Disc 2) (2M) (Track 1).bin'),
    ('D3', r'Azel - Panzer Dragoon RPG (Japan) (Disc 3) (2M)\Azel - Panzer Dragoon RPG (Japan) (Disc 3) (2M) (Track 1).bin'),
    ('D4', r'Azel - Panzer Dragoon RPG (Japan) (Disc 4) (2M, 3M)\Azel - Panzer Dragoon RPG (Japan) (Disc 4) (2M, 3M) (Track 1).bin'),
]


def main():
    files = {}
    for tag, rel in DISCS:
        p = os.path.join(ROOT, rel)
        iso = Iso(p)
        files[tag] = {n.lstrip('/'): s for n, l, s in iso.walk()
                      if not n.endswith('/')}
        c = collections.Counter(n.rsplit('.', 1)[-1].upper()
                                for n in files[tag] if '.' in n)
        print('%s  파일 %d개  %s' % (tag, len(files[tag]),
                                   dict(c.most_common(10))))
    print()
    d1 = files['D1']
    for tag in ('D2', 'D3', 'D4'):
        only = sorted(set(files[tag]) - set(d1))
        print('%s 에만 있는 파일 %d개' % (tag, len(only)))
        for n in only[:40]:
            print('   %-22s %10d B' % (n, files[tag][n]))
    print()
    print('== .EPK 목록 ==')
    for tag in files:
        eps = sorted(n for n in files[tag] if n.upper().endswith('.EPK'))
        print('%s  %d개  %s' % (tag, len(eps), ', '.join(eps)))


if __name__ == '__main__':
    main()

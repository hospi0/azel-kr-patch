# -*- coding: utf-8 -*-
"""지명 상자 탐침 — 그 자리에 «index 를 아는» 토큰을 순서대로 박아 넣는다.

지명 상자가 첫 토큰만 엉뚱하게 그린다(실기 2026-08-15: 「캠프」→「가프」,
「카라반」→「가·깨짐·라·반」). 추측 대신 **index → 화면 글자** 대응을 직접
읽기 위해, 카라반 자리에 base index 0x20,0x21,0x22,0x23,0x24 를 박는다.
화면에 뜬 다섯 글자를 `work/charmap.tsv` 와 대조하면 상자의 해석이 확정된다.

  python probe_place.py <패치된 Track1.bin>
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from iso9660 import Iso, SECTOR, DATA_OFF, DATA_LEN
import cdrom_ecc

TARGET = ('1ST_READ.PRG', 0x3D43E, 11)
PROBE = bytes.fromhex('8020802180228023802400')


def main():
    path = sys.argv[1]
    iso = Iso(path)
    ents = {p.lstrip('/'): (l, s) for p, l, s in iso.walk() if not p.endswith('/')}
    name, off, ln = TARGET
    lba, size = ents[name]
    print('현재 : %s' % iso.read(lba, size)[off:off + ln].hex(' '))
    assert len(PROBE) == ln, '길이 불일치'

    ranges = []
    with open(path, 'r+b') as f:
        for k in range(ln):
            fo = off + k
            sec = lba + fo // DATA_LEN
            ino = fo % DATA_LEN
            abs_off = sec * SECTOR + DATA_OFF + ino
            f.seek(abs_off)
            f.write(PROBE[k:k + 1])
            ranges.append((abs_off, 1))
        n = cdrom_ecc.fix_sectors(f, ranges)
    print('탐침 : %s   (EDC/ECC 재계산 %s섹터)' % (PROBE.hex(' '), n))

    # 되읽기
    chk = Iso(path).read(lba, size)[off:off + ln]
    print('되읽기: %s  %s' % (chk.hex(' '), 'OK' if chk == PROBE else '★불일치'))
    # 이 index 들이 어떤 글자로 구워져 있는지
    cm = {}
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'work', 'charmap.tsv')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            f.readline()
            for line in f:
                c = line.rstrip('\n').split('\t')
                if len(c) == 3 and c[0] == 'base':
                    cm[int(c[2])] = c[1]
    print('기대(우리 배정): ' + ' '.join('%02X=%s' % (i, cm.get(i, '?'))
                                         for i in range(0x20, 0x25)))


if __name__ == '__main__':
    main()

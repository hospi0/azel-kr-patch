# -*- coding: utf-8 -*-
"""`.EPK` 자막을 «자체 폰트»로 판독해 사람이 읽는 일본어로 뽑는다.

  python tools/epk_read.py <Track1.bin> > work/epk_read.tsv

EPK 는 머리 `0x28` 에 `.FNT` 와 같은 꼴의 자체 폰트를 품는다
(`BE16 글리프수 + BE16 0x0004 + 14B 0 + N×32B`). 글리프 수는 그 EPK 자막이
쓰는 «최대 장면 index + 1» 과 맞는다 — 이게 검산이다.

한자는 **비트맵을 기존 글리프 사전(8,830자)에 대조**해 자동 판독한다.
같은 글자는 어느 폰트에서든 같은 32B 비트맵이므로 이 방법이 통한다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import glyphdict
import scan_epk
import strtab


def font_of(data):
    n, tag = struct.unpack_from('>HH', data, 0x28)
    if tag != 0x0004 or not (0 < n < 4000):
        return []
    s = 0x28 + 4 + 14
    return [data[s + i * 32: s + (i + 1) * 32] for i in range(n)]


def main():
    from iso9660 import Iso
    iso = Iso(sys.argv[1])
    dic = glyphdict.build('work/uniq')
    print('# 글리프 사전 %d개' % len(dic), file=sys.stderr)

    print('epk\toffset\tlen\ttext')
    tot = unread = 0
    for name, lba, size in iso.walk():
        if not name.upper().endswith('.EPK'):
            continue
        data = iso.read(lba, size)
        glyphs = font_of(data)
        tab = [dic.get(g, None) for g in glyphs]
        res = scan_epk.scan(data, len(glyphs))
        mx = -1
        for o, ln, _ in res:
            t, _ = strtab.parse_table(data, o, 0x8000, lenient=False)
            for k, v in t[0][2]:
                if k in ('g', 'g1') and v >= 256:
                    mx = max(mx, v - 256)
        print('# %-12s 폰트 %3d글리프 / 자막이 쓰는 최대 index %3d → %s'
              % (name, len(glyphs), mx,
                 'OK' if mx + 1 <= len(glyphs) else '★모자람'), file=sys.stderr)
        for o, ln, _ in res:
            t, _ = strtab.parse_table(data, o, 0x8000, lenient=False)
            s = []
            for k, v in t[0][2]:
                if k not in ('g', 'g1'):
                    continue
                if v < 256:
                    s.append(basemap.ch(v))
                else:
                    c = tab[v - 256] if v - 256 < len(tab) else None
                    if c is None:
                        unread += 1
                        c = '【%d】' % (v - 256)
                    s.append(c)
            tot += 1
            print('%s\t%06X\t%d\t%s' % (name.strip('/'), o, ln, ''.join(s)))
    print('# 자막 %d개, 미판독 글리프 %d개' % (tot, unread), file=sys.stderr)


if __name__ == '__main__':
    main()

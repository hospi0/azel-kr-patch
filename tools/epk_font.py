# -*- coding: utf-8 -*-
"""`.EPK` 머리에 든 자체 폰트를 그려 본다.

  python tools/epk_font.py work/E011.EPK [시작오프셋]

`.FNT` 와 같은 꼴로 보인다: `BE16 글리프수 + BE16 0x0004 + 14B 0 + N×32B`
(32B = 16행 × BE16, 잉크 12×11 / 셀 16×16).
EPK 가 쓰는 최대 장면 index + 1 과 글리프 수가 맞는지 검산할 것.
"""
import struct
import sys


def show(data, base, n, start):
    for g in range(n):
        o = start + g * 32
        rows = struct.unpack('>16H', data[o:o + 32])
        print('--- index %d (파일 %06X)' % (g, o))
        for r in rows:
            print('   ' + ''.join('#' if r & (1 << (15 - b)) else '.'
                                  for b in range(16)))


def main():
    p = sys.argv[1]
    data = open(p, 'rb').read()
    base = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x28
    n, tag = struct.unpack_from('>HH', data, base)
    print('%s @%06X → 글리프 %d개, tag=0x%04X' % (p, base, n, tag))
    show(data, base, min(n, 8), base + 4 + 14)


if __name__ == '__main__':
    main()

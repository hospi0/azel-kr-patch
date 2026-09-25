# -*- coding: utf-8 -*-
"""US 아이템 이름표를 뽑아 JP 표와 나란히 놓는다.

  python tools/us_items.py

JP  `COMMON.DAT 0x00C8D8~` 반각 JIS X0201
US  `COMMON.DAT 0x00CCF0~` 평문 ASCII

★영문 이름은 «A~Z 글리프»만 쓰므로 한글 음절 예산을 **전혀 먹지 않는다**
  (index 190~215 는 원본 그대로 유지되는 칸이다).
⚠단 US 이름이 JP 자리보다 길 수 있다 — 자리를 넘으면 줄여야 한다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import halfwidth as hw

JP_START, JP_END = 0x00C8D8, 0x00CF90
US_START, US_END = 0x00CCF0, 0x00D5D8


def walk(data, start, end, dec):
    """★레코드를 «4바이트 정렬»로 걸어야 한다 — 빈 이름도 한 칸을 차지하므로
    널을 건너뛰며 읽으면 그 자리만큼 표가 밀린다(US 에서 실제로 밀렸다)."""
    out = []
    p = start
    while p < end:
        j = p
        while j < end and data[j] != 0:
            j += 1
        raw = data[p:j]
        nxt = (j + 1 + 3) & ~3
        out.append((p, dec(raw), nxt - p))
        p = nxt
    return out


def dec_jp(raw):
    o = []
    for b in raw:
        if 0x20 <= b < 0x7F:
            o.append(chr(b))
        elif hw.HALF_BASE <= b <= 0xDF:
            o.append(hw.HALF[b - hw.HALF_BASE])
        else:
            o.append('<%02X>' % b)
    return ''.join(o)


def jp_names(path='work/uniq/COMMON.DAT'):
    data = open(path, 'rb').read()
    return walk(data, JP_START, JP_END, dec_jp)


def us_names(path='work/us1/COMMON.DAT'):
    data = open(path, 'rb').read()
    return walk(data, US_START, US_END,
                lambda raw: raw.decode('ascii', 'replace'))


def main():
    jp = jp_names()
    us = us_names()
    print('JP %d개 / US %d개' % (len(jp), len(us)))
    n = min(len(jp), len(us))
    over = 0
    for i in range(n):
        (jo, js, jr), (uo, us_s, ur) = jp[i], us[i]
        need = len(us_s) + 1
        mark = '' if need <= jr else '  ★자리초과 %d>%d' % (need, jr)
        if need > jr:
            over += 1
        print('%3d  %06X %-14s | %-20s%s' % (i, jo, js, us_s, mark))
    print('\n자리 초과 %d / %d' % (over, n))


if __name__ == '__main__':
    main()

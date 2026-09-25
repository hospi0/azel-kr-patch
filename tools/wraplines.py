# -*- coding: utf-8 -*-
"""«엔진이 강제로 접은 뒤의 줄 수»로 초과를 센다.

  python tools/wraplines.py [--width N] [--list 모듈]

★실기 실측(MENUBK 읽을거리): 창이 **17칸에서 문자 단위로 강제 줄바꿈**한다.
  「구세기의 산물을 공연히 두려워하 / 며,」 처럼 **낱말 중간에서 끊긴다**.
  그러니 제약은 「줄 폭」이 아니라 **접은 뒤의 줄 수**다 — 페이지(1/3)가
  고정이라 줄이 늘면 아래가 다음 장으로 밀린다.

  즉 안전 조건 = wrap(번역, 17) 줄 수 ≤ wrap(원문, 17) 줄 수.
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

NL = chr(92) + 'n'
TOK = re.compile(r'<!?[0-9A-Fa-f]{2}>|(.)', re.S)
WIDTH = 17


def cells(s):
    return sum(1 for m in TOK.finditer(s) if m.group(1))


def wrapped_lines(text, width):
    """엔진처럼 «문자 단위»로 접었을 때의 줄 수."""
    n = 0
    for seg in text.split(NL):
        c = cells(seg)
        n += max(1, -(-c // width))
    return n


def main():
    width = WIDTH
    if '--width' in sys.argv:
        width = int(sys.argv[sys.argv.index('--width') + 1])
    ko = {}
    with open('work/trans/ko.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 2 and p[1]:
                ko[p[0]] = p[1]
    units = []
    with open('work/trans/units.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 6:
                units.append(p)
    mods = collections.defaultdict(set)
    with open('work/trans/places.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 7:
                mods[p[0]].add(p[2])

    over = collections.defaultdict(list)
    for r in units:
        k = ko.get(r[5])
        if not k or k == r[5]:
            continue
        j = wrapped_lines(r[5], width)
        m = wrapped_lines(k, width)
        if m > j:
            for mod in mods.get(r[0], ()):
                over[mod].append((m - j, j, m, r[5], k))
                break
    print('접기 폭 %d칸 기준' % width)
    print('%-10s %6s' % ('모듈', '줄 초과'))
    tot = 0
    for m in sorted(over, key=lambda x: -len(over[x])):
        print('%-10s %6d' % (m, len(over[m])))
        tot += len(over[m])
    print('\n합계 %d건' % tot)
    if '--list' in sys.argv:
        want = sys.argv[sys.argv.index('--list') + 1]
        for d, j, mm, jp, k in sorted(over.get(want, []), reverse=True)[:30]:
            print('  +%d줄 (원문%d→번역%d) %s' % (d, j, mm, k[:70]))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""EPK 번역표 전수 검사 — 예산 초과를 «한 번에» 뽑는다.

  python tools/epk_check.py

한 건씩 고쳐 다시 돌리면 끝이 없다. 넘치는 것을 전부 세어 놓고 한 회차에 고친다.
"""
import re
import sys

TOK = re.compile(r'<!([0-9A-F]{2})>|<([0-9A-F]{2})>|\\n|(.)', re.S)


def nbytes(s):
    n = 1
    for m in TOK.finditer(s):
        n += 1 if (m.group(1) or m.group(2) or m.group(0) == '\\n') else 2
    return n


def main():
    lim = {}
    with open('work/epk_units.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 7:
                lim[(p[0], p[1], p[2])] = int(p[3])
    bad = []
    n = 0
    with open('work/epk_ko.tsv', encoding='utf-8') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) < 4 or not p[3]:
                continue
            n += 1
            key = (p[0], p[1], p[2])
            if key not in lim:
                print('★스냅샷에 없음:', key)
                continue
            b = nbytes(p[3])
            if b > lim[key]:
                bad.append((b - lim[key], (lim[key] - 1) // 2, p))
    print('번역 %d개 / 예산 초과 %d개' % (n, len(bad)))
    for over, maxch, p in sorted(bad, reverse=True):
        print('D%s %-10s %s  %2d칸까지  (%+d B)  %s'
              % (p[0], p[1], p[2], maxch, over, p[3]))


if __name__ == '__main__':
    main()

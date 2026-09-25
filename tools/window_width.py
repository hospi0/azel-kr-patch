# -*- coding: utf-8 -*-
"""고정창 폭을 «모듈별 원문 최대 줄 폭»으로 잡아 초과를 센다.

  python tools/window_width.py [--list 모듈]

★«문자열별 원문 칸»을 상한으로 쓰면 과잉이다 — `帝国の話`(4칸) 같은 짧은
  메뉴 항목까지 4칸으로 묶이는데, 실제로 `話をやめる`(5칸)를 「이야기 그만」(6칸)
  으로 넣고도 멀쩡했다. 그 창은 훨씬 넓다.
  창 폭은 알 수 없지만 **원문이 그 창에서 가장 길게 쓴 줄** 만큼은 확실히 된다.
  → 모듈별 최대 원문 줄 폭을 하한 추정치로 쓴다. 그걸 넘는 것만 위험하다.
  ⚠이것도 «추정»이다. 확정하려면 실기 스샷으로 재야 한다.
    → [[feedback_screen_limits_measure_not_derive]]
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

NL = chr(92) + 'n'
TOK = re.compile(r'<!?[0-9A-Fa-f]{2}>|(.)', re.S)
KINDS = {'ui', 'slot'}


def cells(s):
    return sum(1 for m in TOK.finditer(s) if m.group(1))


def load():
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
    return ko, units, mods


def main():
    ko, units, mods = load()
    wid = collections.Counter()
    for r in units:
        if r[1] not in KINDS:
            continue
        m = max(cells(x) for x in r[5].split(NL))
        for mod in mods.get(r[0], ()):
            wid[mod] = max(wid[mod], m)

    over = collections.defaultdict(list)
    for r in units:
        k = ko.get(r[5])
        if r[1] not in KINDS or not k or k == r[5]:
            continue
        km = max(cells(x) for x in k.split(NL))
        for mod in mods.get(r[0], ()):
            if km > wid[mod]:
                over[mod].append((km - wid[mod], r[0], r[5], k))
                break

    print('%-10s %6s %6s' % ('모듈', '창폭', '초과'))
    tot = 0
    for m in sorted(wid, key=lambda x: -len(over[x])):
        if not over[m]:
            continue
        print('%-10s %6d %6d' % (m, wid[m], len(over[m])))
        tot += len(over[m])
    print('\n합계 초과 %d건' % tot)

    if '--list' in sys.argv:
        want = sys.argv[sys.argv.index('--list') + 1]
        for d, uid, jp, k in sorted(over.get(want, []), reverse=True):
            print('  +%-2d 창%-3d %s' % (d, wid[want], k[:76]))


if __name__ == '__main__':
    main()

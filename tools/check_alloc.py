# -*- coding: utf-8 -*-
"""슬롯 재배정 검산 — 번역문이 쓰는 «고유 음절»이 슬롯 안에 들어가나.

  python tools/check_alloc.py

글리프 공간은 두 층(§7.7):
    기본 폰트 0~255 중 «갈아끼울 수 있는» 칸 (1바이트 구간 + 나머지)
    장면 FNT   256~  — **그 모듈이 쓰는 자리만큼**, 모듈마다 따로

기본 폰트에 못 들어간 글자는 그 글자를 쓰는 **모든 모듈**의 FNT 에 들어가야 한다.
모듈 하나라도 «기본 여유 + 그 FNT 크기»를 넘으면 빌드가 깨진다.
"""
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import alloc
import basemap
import fnt as fntmod

D = 'work/uniq'


def main():
    ko = {}
    with open('work/trans/ko.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 2 and p[1]:
                ko[p[0]] = p[1]

    # 단위 → 그 단위가 나오는 (모듈, FNT)
    places = defaultdict(list)
    idx = {}
    with open('work/trans/units.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 6:
                idx[p[0]] = p[5]
    with open('work/trans/places.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 7:
                places[p[0]].append((p[2], p[3]))

    unit_texts = {uid: ko[jp] for uid, jp in idx.items() if jp in ko}
    fnt_sizes = {f[:-4]: len(fntmod.parse(open(os.path.join(D, f), 'rb').read()))
                 for f in os.listdir(D) if f.endswith('.FNT')}

    one, two = alloc.base_capacity()
    base_map, scene_map = alloc.allocate(unit_texts, places, fnt_sizes)

    chars = Counter()
    for uid, t in unit_texts.items():
        for c in t:
            if c not in basemap.REVERSE_KEEP:
                chars[c] += 1
    print('번역문 고유 글자 %d개  (기본 폰트 칸 = 1바이트 %d + 2바이트 %d = %d)'
          % (len(chars), one, two, one + two))
    print('기본 폰트 배정 %d, 넘친 글자 %d' % (len(base_map), len(chars) - len(base_map)))

    bad = []
    for fn, m in sorted(scene_map.items()):
        cap = fnt_sizes.get(fn)
        if cap is None:
            continue
        if len(m) > cap:
            bad.append((fn, len(m), cap))
    print('장면 FNT %d개 중 넘친 것 %d개' % (len(scene_map), len(bad)))
    for fn, n, cap in sorted(bad, key=lambda x: x[2] - x[1])[:25]:
        print('   %-10s 필요 %4d / 자리 %4d   (%+d)' % (fn, n, cap, cap - n))
    if not bad:
        print('✅ 모든 모듈이 슬롯 안에 들어간다')


if __name__ == '__main__':
    main()

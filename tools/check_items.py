# -*- coding: utf-8 -*-
"""아이템 이름 번역 검사 — 자리(바이트)와 «서로 다른 음절 수».

  python tools/check_items.py [work/trans/items.tsv]

★반각 이름표는 글자 하나가 **1바이트**다. 그리고 쓸 수 있는 글리프 자리가
  99칸뿐인데 그중 43칸은 숫자·영문·부호로 묶여 있으므로,
  **한글은 서로 다른 56음절**까지만 쓸 수 있다.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import alloc
import basemap
import halfwidth as hw

FREE = [i for i in hw.usable_indices() if i not in alloc.KEEP]
KEEPCH = {basemap.ch(i): i for i in hw.usable_indices() if i in alloc.KEEP}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'work/trans/items.tsv'
    rows = []
    with open(path, encoding='utf-8') as f:
        f.readline()
        for line in f:
            line = line.rstrip('\n')
            if line:
                rows.append(line.split('\t'))

    syl = Counter()
    over = []
    for r in rows:
        if len(r) < 5 or not r[4]:
            continue
        off, jp, nb, room, ko = r[0], r[1], int(r[2]), int(r[3]), r[4]
        need = len(ko) + 1                   # 반각 1바이트/글자 + 종단
        if need > room:
            over.append((off, jp, ko, need, room))
        for c in ko:
            if c in KEEPCH:                  # 숫자·영문·부호는 공짜
                continue
            syl[c] += 1

    print('번역된 이름 %d / %d' % (sum(1 for r in rows if len(r) > 4 and r[4]),
                                  len(rows)))
    print('한글 등 «새 글리프»가 필요한 서로 다른 글자 = %d종' % len(syl))
    print('쓸 수 있는 자리 = %d칸  → %s'
          % (len(FREE),
             'OK, %d칸 남음' % (len(FREE) - len(syl)) if len(syl) <= len(FREE)
             else '★%d종 초과' % (len(syl) - len(FREE))))

    if over:
        print('\n★자리 초과 %d건:' % len(over))
        for off, jp, ko, need, room in over[:20]:
            print('   %s %-14s → %-14s %d>%d' % (off, jp, ko, need, room))

    print('\n음절 빈도(적게 쓰이는 것부터 — 줄이려면 여기부터):')
    rare = syl.most_common()[::-1]
    print('  ', ' '.join('%s%d' % (c, n) for c, n in rare[:60]))
    return syl


if __name__ == '__main__':
    main()

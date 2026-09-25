# -*- coding: utf-8 -*-
"""화면 폭 초과 집계 — «절대 상한»과 «원문 대비» 둘로 나눠 센다.

  python tools/overflow.py [--list 갈래]

★두 규칙은 세기가 다르다.
    절대 상한   실기에서 실제로 잘리는 칸 수(실측). 넘으면 **반드시 깨진다**.
    원문 대비   원본이 들어갔으니 그 이하면 안전. 넘어도 잘린다는 뜻은 아니다.
  먼저 절대 상한부터 없애고, 그다음 원문 대비를 줄이는 게 순서다.
"""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))

TOK = re.compile(r'<!([0-9A-Fa-f]{2})>|<([0-9A-Fa-f]{2})>|(.)', re.S)
NL = chr(92) + 'n'

# 실기 실측 상한(§세션4).
HARD = {'dialog': 19, 'narration': 19, 'movie': 19}
# ★slot 은 갈래 전체가 12칸이 아니다 — 12칸은 «세이브 메뉴»에서 잰 값이고,
#   마을의 「소문」 선택지 슬롯은 창이 더 넓다. 갈래로 뭉뚱그려 12를 걸면
#   원문 19칸짜리 선택지가 전부 거짓 초과로 잡힌다(41건이 그랬다).
#   → 세이브 계열 모듈만 12칸, 나머지 슬롯은 «원문 대비»로 본다.
SAVE_MODULES = {'SAVE', '1ST_READ'}
SAVE_CELLS = 12
# ⛔`ui`·`slot` 을 «문자열별 원문 칸»으로 묶으면 **과잉이다** — `帝国の話`(4칸)를
#   「제국 이야기」(6칸)로 넣은 것까지 위반이 된다. 실제로 `話をやめる`(5칸)를
#   「이야기 그만」(6칸)으로 넣고도 멀쩡했다. 그 창은 훨씬 넓다.
#   고정창은 **창마다 따로, 실측으로** 봐야 한다. 확정된 것:
#     · MENUBK 읽을거리   17칸 × 7줄  → `reflow_menubk.py`
#     · 기술 설명 바      16칸(원문 31건이 전부 정확히 16칸) → 그 무리만 검사
#     · 세이브 선택지     12칸
FIXED_WINDOW = set()


def cells(seg):
    return sum(1 for m in TOK.finditer(seg) if m.group(3) is not None)


def main():
    ko = {}
    with open('work/trans/ko.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 2 and p[1]:
                ko[p[0]] = p[1]

    units = []
    with open('work/trans/units.tsv', encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 6:
                units.append(p)

    mods = {}
    with open('work/trans/places.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 7:
                mods.setdefault(p[0], set()).add(p[2])

    hard, soft = [], []
    ch = Counter()
    for p in units:
        uid, kind, jp = p[0], p[1], p[5]
        k = ko.get(jp)
        if not k or k == jp:
            continue
        jl = [cells(s) for s in jp.split(NL)]
        kl = [cells(s) for s in k.split(NL)]
        lim = HARD.get(kind)
        if kind in FIXED_WINDOW:
            lim = max(jl)                 # 고정창 = 원문 칸이 상한
        if kind == 'slot' and mods.get(uid, set()) & SAVE_MODULES:
            lim = min(lim or SAVE_CELLS, SAVE_CELLS)
        if lim and max(kl) > lim:
            hard.append((max(kl) - lim, kind, jp, k))
            ch[kind] += 1
        elif max(kl) > max(jl):
            soft.append((max(kl) - max(jl), kind, jp, k))

    print('★절대 상한 초과 %d건 (실기에서 잘린다)' % len(hard))
    print('   갈래별:', dict(ch.most_common()))
    print('△원문 대비만 초과 %d건' % len(soft))

    if '--snap' in sys.argv:
        # ★키(원문)를 손으로 옮겨 적으면 오타로 깨진다 — 스냅샷에서 가져온다.
        with open('work/over_snap.tsv', 'w', encoding='utf-8', newline='') as f:
            f.write('idx\tkind\tlimit\tover\tjp\tko\n')
            for i, (over, kind, jp, k) in enumerate(sorted(hard, reverse=True)):
                if kind in FIXED_WINDOW:
                    lim = max(cells(s) for s in jp.split(NL))
                else:
                    lim = HARD.get(kind, 0)
                f.write('%d\t%s\t%d\t%d\t%s\t%s\n' % (i, kind, lim, over, jp, k))
        print('→ work/over_snap.tsv (%d행)' % len(hard))

    if '--list' in sys.argv:
        want = sys.argv[sys.argv.index('--list') + 1]
        for over, kind, jp, k in sorted(hard, reverse=True):
            if want in ('all', kind):
                print('+%-2d %-9s %s\n        %s' % (over, kind, jp[:60], k[:70]))


if __name__ == '__main__':
    main()

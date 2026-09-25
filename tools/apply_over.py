# -*- coding: utf-8 -*-
"""줄인 번역을 되먹인다 — `work/over_snap.tsv` 의 idx 를 키로.

  python tools/apply_over.py work/over1.tsv [work/over2.tsv ...]

수정 파일 형식 = `idx <TAB> 새 번역`.
★원문(키)은 스냅샷에서 가져온다 — 손으로 옮겨 적으면 오타로 키가 깨진다.
바꾼 뒤 반드시 `merge_kr.py` → `overflow.py` 로 다시 잰다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import overflow

SNAP = 'work/over_snap.tsv'
KRDIR = 'work/trans/kr'


def main():
    jp_of, lim_of = {}, {}
    with open(SNAP, encoding='utf-8') as f:
        f.readline()
        for line in f:
            r = line.rstrip('\n').split('\t')
            if len(r) >= 6:
                jp_of[r[0]] = r[4]
                lim_of[r[0]] = int(r[2])

    new = {}
    for p in sys.argv[1:]:
        with open(p, encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if not line or '\t' not in line:
                    continue
                i, ko = line.split('\t', 1)
                i = i.strip()
                if i not in jp_of:
                    print('⚠스냅샷에 없는 idx: %s' % i)
                    continue
                new[jp_of[i]] = (ko, lim_of[i])

    # 넣기 전에 칸 검사 — 넘치면 아예 안 넣는다
    bad = [(jp, ko, lim) for jp, (ko, lim) in new.items()
           if max(overflow.cells(s) for s in ko.split(overflow.NL)) > lim]
    for jp, ko, lim in bad:
        print('★아직 초과(%d칸 > %d): %s' % (
            max(overflow.cells(s) for s in ko.split(overflow.NL)), lim, ko))
    if bad:
        raise SystemExit('넣지 않았다 — 위 %d건을 더 줄일 것' % len(bad))

    hit = 0
    for fn in sorted(os.listdir(KRDIR)):
        if not fn.endswith('.tsv'):
            continue
        p = os.path.join(KRDIR, fn)
        lines = open(p, encoding='utf-8').read().split('\n')
        out = []
        for i, l in enumerate(lines):
            r = l.split('\t')
            if i and len(r) >= 7 and r[5] in new:
                r[6] = new[r[5]][0]
                hit += 1
            out.append('\t'.join(r))
        open(p, 'w', encoding='utf-8', newline='').write('\n'.join(out))
    print('%d개 단위 → %d행 반영' % (len(new), hit))


if __name__ == '__main__':
    main()

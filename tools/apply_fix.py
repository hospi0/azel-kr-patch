# -*- coding: utf-8 -*-
"""줄인 번역을 번역 파일에 되먹인다.

  python tools/apply_fix.py work/fails_snap.tsv work/fix1.tsv work/fix2.tsv ...

수정 파일 형식 = `인덱스 <TAB> 새 번역`.
인덱스는 `fails_snap.tsv` 의 행 번호다 — 원문을 손으로 옮겨 적으면 오타로
키가 깨지므로(실제로 `回復`→`回복` 사고를 냈다) **원문은 스냅샷에서 가져온다**.
`=` 는 «원문 그대로 두기»(번역 대상이 아니라고 판정한 것).
"""
import os
import sys


def main():
    snap = sys.argv[1]
    jp_of = {}
    with open(snap, encoding='utf-8') as f:
        f.readline()
        for line in f:
            r = line.rstrip('\n').split('\t')
            if len(r) >= 5:
                jp_of[r[0]] = r[3]

    new = {}
    for p in sys.argv[2:]:
        with open(p, encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if not line or '\t' not in line:
                    continue
                i, ko = line.split('\t', 1)
                jp = jp_of.get(i.strip())
                if jp is None:
                    print('★스냅샷에 없는 인덱스: %s' % i)
                    continue
                new[jp] = jp if ko.strip() == '=' else ko

    krdir = 'work/trans/kr'
    n = 0
    for fn in sorted(os.listdir(krdir)):
        if not fn.endswith('.tsv'):
            continue
        path = os.path.join(krdir, fn)
        with open(path, encoding='utf-8') as f:
            lines = f.read().split('\n')
        out = []
        for i, line in enumerate(lines):
            if i == 0 or not line:
                out.append(line)
                continue
            r = line.split('\t')
            if len(r) >= 7 and r[5] in new:
                r[6] = new[r[5]]
                n += 1
            out.append('\t'.join(r))
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write('\n'.join(out))
    print('수정 %d종 → %d행 반영' % (len(new), n))


if __name__ == '__main__':
    main()

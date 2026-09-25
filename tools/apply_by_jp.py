# -*- coding: utf-8 -*-
"""«원문 ↦ 새 번역» 표를 번역 파일에 되먹인다.

  python tools/apply_by_jp.py work/menubk_reflow.tsv [...]

`apply_over.py` 는 스냅샷의 idx 를 키로 쓰지만, 이건 **원문 자체**가 키다
(도구가 원문을 그대로 뱉은 표에 쓴다 — 손으로 옮겨 적지 않으므로 안전).
"""
import os
import sys

KRDIR = 'work/trans/kr'


def main():
    new = {}
    for p in sys.argv[1:]:
        with open(p, encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if '\t' not in line:
                    continue
                jp, ko = line.split('\t', 1)
                new[jp] = ko
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
                r[6] = new[r[5]]
                hit += 1
            out.append('\t'.join(r))
        open(p, 'w', encoding='utf-8', newline='').write('\n'.join(out))
    print('%d개 단위 → %d행 반영' % (len(new), hit))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""추출기를 고친 뒤 «이미 한 번역»을 새 번역표로 옮긴다.

  python tools/port_trans.py work/trans/kr

배경: PRG 도 구간마다 폰트가 다르다는 걸 뒤늦게 알아 원문 판독이 바뀌었다
(`textmodel2.shared_region_fonts`). 원문 텍스트가 번역표의 **키**이므로,
바뀐 원문에 붙어 있던 번역은 자리를 잃는다.

하는 일
  1. 옛 `units.tsv.old` + `places.tsv.old` 로 «(모듈, 오프셋) → 옛 원문» 을,
     새 `units.tsv` + `places.tsv` 로 «(모듈, 오프셋) → 새 원문» 을 만든다.
  2. 두 표를 이어 «옛 원문 → 새 원문» 대응을 얻는다.
  3. 번역 파일의 `jp` 열을 새 원문으로 바꾼다.
     원문이 **달라진 행은 번역을 비우고** 목록으로 알린다 —
     깨진 일본어를 보고 한 번역이라 그대로 두면 안 된다.
"""
import os
import sys
from collections import defaultdict


def load(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        for line in f:
            line = line.rstrip('\n')
            if line:
                rows.append(line.split('\t'))
    return head, rows


def place_map(units, places):
    """(src, module, off) → 원문"""
    jp = {u[0]: u[5] for u in units}
    m = {}
    for p in places:
        if len(p) >= 5 and p[0] in jp:
            m[(p[1], p[2], p[4])] = jp[p[0]]
    return m


def main():
    krdir = sys.argv[1] if len(sys.argv) > 1 else 'work/trans/kr'
    root = 'work/trans'

    _, ou = load(os.path.join(root, 'units.tsv.old'))
    _, op = load(os.path.join(root, 'places.tsv.old'))
    _, nu = load(os.path.join(root, 'units.tsv'))
    _, np_ = load(os.path.join(root, 'places.tsv'))

    old = place_map(ou, op)
    new = place_map(nu, np_)

    old2new = defaultdict(set)
    for k, v in old.items():
        if k in new:
            old2new[v].add(new[k])

    ambiguous = {k: v for k, v in old2new.items() if len(v) > 1}
    print('옛 원문 %d종 → 새 원문 대응 (모호 %d종)'
          % (len(old2new), len(ambiguous)))

    newmeta = {u[5]: u for u in nu}

    changed, kept, lost = [], 0, []
    for fn in sorted(f for f in os.listdir(krdir) if f.endswith('.tsv')):
        path = os.path.join(krdir, fn)
        with open(path, encoding='utf-8') as f:
            head = f.readline()
            lines = [l.rstrip('\n') for l in f if l.strip()]
        out = [head.rstrip('\n')]
        for ln, line in enumerate(lines, 2):
            r = line.split('\t')
            if len(r) < 6:
                out.append(line)
                continue
            jp, ko = r[5], (r[6] if len(r) > 6 else '')
            cand = old2new.get(jp)
            if not cand:
                lost.append((fn, ln, jp))
                out.append(line)
                continue
            njp = sorted(cand)[0]
            meta = newmeta.get(njp)
            if njp != jp:
                changed.append((fn, ln, jp, njp, ko))
                ko = ''                      # 깨진 원문 기준 번역 → 폐기
            if meta:
                r = [meta[0], meta[1], meta[2], meta[3], meta[4], njp, ko]
            else:
                r = r[:5] + [njp, ko]
            if ko:
                kept += 1
            out.append('\t'.join(r))
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write('\n'.join(out) + '\n')

    print('\n살린 번역 %d행 / 원문이 바뀌어 비운 번역 %d행 / 대응 못 찾음 %d행'
          % (kept, len(changed), len(lost)))
    if changed:
        print('\n★다시 번역해야 하는 행 (원문이 잘못 읽혔던 자리):')
        for fn, ln, jp, njp, ko in changed:
            print('  %s:%d' % (fn, ln))
            print('     옛(틀림): %s' % jp[:62])
            print('     새(맞음): %s' % njp[:62])
    if lost:
        print('\n⚠새 표에서 못 찾은 원문 %d행 (표본 5)' % len(lost))
        for fn, ln, jp in lost[:5]:
            print('   %s:%d %s' % (fn, ln, jp[:50]))


if __name__ == '__main__':
    main()

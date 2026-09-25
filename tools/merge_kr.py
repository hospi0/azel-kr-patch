# -*- coding: utf-8 -*-
"""번역 파일들 → 최종 번역표 `ko.tsv` 병합 + 남은 일 목록.

  python tools/merge_kr.py [work/trans/kr]

★키는 «원문 텍스트»다. 같은 원문이 여러 분할 파일에 나올 수 있으므로
  (표를 다시 만들며 단위가 합쳐지면 생긴다) **비어 있지 않은 번역**을 취한다.
  둘 다 채워져 있는데 내용이 다르면 충돌로 보고한다 — 자동으로 고르지 않는다.

산출
  work/trans/ko.tsv      jp → ko  (빌더 입력)
  work/trans/todo.tsv    아직 번역 안 된 단위 (units.tsv 형식 그대로)
"""
import os
import sys
from collections import defaultdict

ROOT = 'work/trans'


def load(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        f.readline()
        for i, line in enumerate(f, 2):
            line = line.rstrip('\n')
            if line:
                rows.append((i, line.split('\t')))
    return rows


def main():
    krdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'kr')

    got = {}
    conflict = []
    seen = defaultdict(list)
    for fn in sorted(f for f in os.listdir(krdir) if f.endswith('.tsv')):
        for ln, r in load(os.path.join(krdir, fn)):
            if len(r) < 6:
                continue
            jp = r[5]
            ko = r[6] if len(r) > 6 else ''
            seen[jp].append(('%s:%d' % (fn, ln), ko))
            if not ko:
                continue
            if jp in got and got[jp] != ko:
                conflict.append((jp, got[jp], ko))
            else:
                got[jp] = ko

    units = load(os.path.join(ROOT, 'units.tsv'))
    total = len(units)
    todo = [(ln, r) for ln, r in units if r[5] not in got]

    # ko.tsv — 번역표에 실제로 있는 원문만 (옛 표의 잔재를 걸러낸다)
    valid = {r[5] for _, r in units}
    stale = [j for j in got if j not in valid]
    with open(os.path.join(ROOT, 'ko.tsv'), 'w', encoding='utf-8', newline='') as f:
        f.write('jp\tko\n')
        for _, r in units:
            if r[5] in got:
                f.write('%s\t%s\n' % (r[5], got[r[5]]))

    with open(os.path.join(ROOT, 'todo.tsv'), 'w', encoding='utf-8', newline='') as f:
        f.write('id\tkind\tcount\tbudget\tchars\tjp\tko\n')
        for _, r in todo:
            f.write('\t'.join(r[:6]) + '\t\n')

    done = total - len(todo)
    print('번역표 %d단위 중 %d단위 번역됨 (%.1f%%), 남은 것 %d단위'
          % (total, done, 100.0 * done / total, len(todo)))
    if stale:
        print('⚠번역표에 없는 옛 원문 %d건은 ko.tsv 에서 뺐다' % len(stale))
    if conflict:
        print('\n★같은 원문에 다른 번역 %d건 — 하나로 정해야 한다' % len(conflict))
        for jp, a, b in conflict[:10]:
            print('   %s' % jp[:44])
            print('      A: %s' % a[:52])
            print('      B: %s' % b[:52])

    from collections import Counter
    c = Counter(r[1] for _, r in todo)
    print('\n남은 것 갈래별:', dict(c.most_common()))
    print('남은 글자 %d자' % sum(int(r[4]) for _, r in todo))
    print('\n→ %s/ko.tsv (%d행) , %s/todo.tsv (%d행)'
          % (ROOT, done, ROOT, len(todo)))


if __name__ == '__main__':
    main()

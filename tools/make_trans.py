# -*- coding: utf-8 -*-
"""번역표를 만든다 — 중복을 묶은 «번역 단위» + 출현 위치 목록.

  python tools/make_trans.py work/uniq work/trans

산출:
  work/trans/units.tsv      번역 단위. **여기 `ko` 열만 채우면 된다.**
  work/trans/places.tsv     각 단위가 나오는 모든 위치 (빌더가 쓴다)

같은 원문이 여러 곳에 있으면 한 줄로 묶는다(전체의 절반가량이 중복이다).
`budget` 은 그 단위가 나오는 **모든 자리 중 가장 빡빡한 값**이다 —
슬롯 크기가 자리마다 다를 수 있으므로 최소값에 맞춰야 한다.
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import textmodel2

# 번역하지 않는 갈래
SKIP = {'asset'}


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    items = textmodel2.collect(src)

    units = {}
    places = defaultdict(list)
    for it in items:
        if it['kind'] in SKIP:
            continue
        key = it['text']
        u = units.get(key)
        if u is None:
            units[key] = dict(kind=it['kind'], budget=it['budget'], n=1,
                              nch=sum(1 for k, _ in it['toks']
                                      if k in ('g', 'g1')))
        else:
            u['n'] += 1
            u['budget'] = min(u['budget'], it['budget'])
            if it['kind'] == 'slot':
                u['kind'] = 'slot'      # 한 자리라도 슬롯이면 슬롯 제약
        places[key].append(it)

    order = sorted(units, key=lambda k: (-units[k]['n'], k))
    with open(os.path.join(out, 'units.tsv'), 'w', encoding='utf-8') as f:
        f.write('id\tkind\tcount\tbudget\tchars\tjp\tko\n')
        for i, k in enumerate(order):
            u = units[k]
            f.write('%d\t%s\t%d\t%d\t%d\t%s\t\n'
                    % (i, u['kind'], u['n'], u['budget'], u['nch'], k))

    idx = {k: i for i, k in enumerate(order)}
    with open(os.path.join(out, 'places.tsv'), 'w', encoding='utf-8') as f:
        f.write('id\tsrc\tmodule\tfnt\toffset\tbudget\tkind\n')
        for k in order:
            for it in places[k]:
                f.write('%d\t%s\t%s\t%s\t%06X\t%d\t%s\n'
                        % (idx[k], it['src'], it['module'], it['fnt'],
                           it['off'], it['budget'], it['kind']))

    from collections import Counter
    c = Counter(units[k]['kind'] for k in units)
    nch = sum(units[k]['nch'] for k in units)
    print('번역 단위 %d개 / %d자   (출현 %d곳)'
          % (len(units), nch, sum(len(v) for v in places.values())))
    print('갈래별:', dict(c.most_common()))
    print('→ %s/units.tsv , places.tsv' % out)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""EPK 자막 → 번역 작업표. 꼬리조각은 «바이트 범위 포함»으로 가린다.

  python tools/epk_units.py work/epk_d1.tsv [...] > work/epk_units.tsv

★꼬리조각 = 다른 문자열의 **바이트 범위 안**에서 시작한 것.
  본문을 번역해 덮으면 그 자리는 사라지므로 **건드리면 안 된다**
  (건드리면 본문 한가운데를 깨뜨린다).
  판정을 「글자가 부분열인가」로 하면 같은 대사가 두 번 나올 때 오판한다.

폰트 칸 재사용의 전제 = **그 EPK 자막을 하나도 빼지 않고 번역**하는 것.
하나라도 남기면 그 글자가 쓰는 칸은 못 쓴다.
"""
import collections
import re
import sys

TOK = re.compile(r'<!?[0-9A-Fa-f]{2}>|(.)', re.S)


def cells(s):
    return sum(1 for m in TOK.finditer(s) if m.group(1))


def main():
    rows = []
    for p in sys.argv[1:]:
        disc = p.rsplit('_d', 1)[-1].split('.')[0]
        with open(p, encoding='utf-8') as f:
            f.readline()
            for line in f:
                r = line.rstrip('\n').split('\t')
                if len(r) >= 4:
                    rows.append([disc] + r)

    by = collections.defaultdict(list)
    for r in rows:
        by[(r[0], r[1])].append(r)

    print('disc\tepk\toffset\tlen\tmax칸\tfrag\tjp')
    n = f = 0
    for key, lst in sorted(by.items()):
        lst.sort(key=lambda r: int(r[2], 16))
        spans = [(int(r[2], 16), int(r[2], 16) + int(r[3])) for r in lst]
        for i, r in enumerate(lst):
            o = int(r[2], 16)
            frag = any(j != i and a < o < b for j, (a, b) in enumerate(spans))
            n += 1
            f += frag
            print('%s\t%s\t%s\t%s\t%d\t%s\t%s'
                  % (r[0], r[1], r[2], r[3], (int(r[3]) - 1) // 2,
                     'Y' if frag else '', r[4]))
    print('# 자막 %d개 / 꼬리조각 %d개 → 번역 대상 %d개' % (n, f, n - f),
          file=sys.stderr)


if __name__ == '__main__':
    main()

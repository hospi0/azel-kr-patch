# -*- coding: utf-8 -*-
"""고유명사 표기 흔들림 전수 검사.

  python tools/name_consistency.py [ko.tsv]

「샤프리」와 「샤플리의 둥지」처럼 **같은 원문 이름이 화면마다 다르게 적힌** 것을 찾는다.

방법
  ① 원문이 «순수 가타카나»인 짧은 항목 = 그 이름의 **표준 표기**(canonical).
  ② 그 가타카나를 **포함하는** 다른 원문을 모두 찾아, 번역문에 표준 표기가
     들어 있는지 본다. 없으면 흔들림 후보.
  ③ 후보의 번역문에서 표준 표기와 «앞 두 글자가 같은» 한글 덩어리를 뽑아
     실제로 어떻게 적혔는지 보여 준다.
"""
import os
import re
import sys
from collections import defaultdict

KATA = re.compile(r'^[゠-ヿ]{3,10}$')
HAN = re.compile(r'[가-힣]+')


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'work/trans/ko.tsv'
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 2 and p[1]:
                rows.append((p[0], p[1]))

    canon = {}
    for jp, ko in rows:
        if KATA.match(jp) and HAN.fullmatch(ko or ''):
            # 같은 원문이 여러 번역을 가지면 그것부터 문제
            if jp in canon and canon[jp] != ko:
                print('★원문 자체가 두 표기: %s → %s / %s' % (jp, canon[jp], ko))
            canon[jp] = ko

    hits = defaultdict(list)
    for jp, ko in rows:
        for name, kname in canon.items():
            if name in jp and jp != name and kname not in ko:
                hits[(name, kname)].append((jp, ko))

    n = 0
    for (name, kname), lst in sorted(hits.items()):
        # 표준 표기와 앞 2글자가 같은 한글 덩어리 = 다르게 적힌 같은 이름
        alts = set()
        for jp, ko in lst:
            for w in HAN.findall(ko):
                if w != kname and w[:2] == kname[:2] and abs(len(w) - len(kname)) <= 3:
                    alts.add(w)
        if not alts:
            continue
        n += 1
        print('\n■ %s = 「%s」  ↔ 다르게 적힘: %s' % (name, kname, ', '.join(sorted(alts))))
        for jp, ko in lst[:6]:
            if any(a in ko for a in alts):
                print('   %s\n      → %s' % (jp[:50], ko[:60]))
    print('\n흔들림 후보 %d건 (고유명사 %d개 대조)' % (n, len(canon)))


if __name__ == '__main__':
    main()

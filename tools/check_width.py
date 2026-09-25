# -*- coding: utf-8 -*-
"""화면 폭 검사 — 번역이 원문보다 «글자 수»로 길어진 곳을 찾는다.

  python tools/check_width.py [movie|ui|dialog|...]

★예산(바이트)과 화면 폭(글자 수)은 **다른 제약**이다. 1바이트 슬롯을 쓰면
  바이트는 줄어도 화면에 찍히는 칸 수는 그대로다 — 예산을 통과해도 잘린다.
  실기 스샷에서 무비 자막 「최대 전속,15분 후 도착이라고 전해라!」(22칸)가
  19칸째에서 잘렸다. 원문은 18칸이었다.

안전 규칙 = **번역 칸 수 ≤ 원문 칸 수**. 원본이 화면에 들어갔으니 그 이하면
들어간다. 줄(`\\n`)마다 따로 센다 — 한 줄이 곧 한 화면 줄이다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

TOK = re.compile(r'<!([0-9A-Fa-f]{2})>|<([0-9A-Fa-f]{2})>|(.)', re.S)
NL = chr(92) + 'n'


def cells(seg):
    """한 줄의 «화면 칸 수» — 제어코드·생바이트는 안 찍히므로 0칸."""
    n = 0
    for m in TOK.finditer(seg):
        if m.group(3) is not None:
            n += 1
    return n


def lines(text):
    return [cells(s) for s in text.split(NL)]


def load(p):
    rows = []
    with open(p, encoding='utf-8') as f:
        f.readline()
        for line in f:
            line = line.rstrip('\n')
            if line:
                rows.append(line.split('\t'))
    return rows


def cell_limit(jp, budget):
    """그 자리에 «그릴 수 있는 최대 칸 수».

    ★원본은 글자를 2바이트 토큰으로 쓴다. 그러니 자리에 들어가는 칸 수는
      `(예산 − 종단 − 제어코드) ÷ 2` 로 정해진다.
      1바이트 토큰을 쓰면 바이트는 남아도 **칸이 원본보다 많아져** 화면에서
      잘린다(실기: 배틀 UI 「…발생시킨다2게이」, 무비 자막 19칸 초과).
    """
    ctrl = sum(1 for m in TOK.finditer(jp) if m.group(3) is None)
    return (budget - 1 - ctrl) // 2


def main():
    kinds = set(sys.argv[1:]) or None
    units = load('work/trans/units.tsv')
    kind_of = {u[5]: u[1] for u in units}
    ko = {r[0]: r[1] for r in load('work/trans/ko.tsv') if len(r) > 1}

    bad = []
    mx = {}
    for jp, k in ko.items():
        kind = kind_of.get(jp, '?')
        if kinds and kind not in kinds:
            continue
        a, b = lines(jp), lines(k)
        mx[kind] = max(mx.get(kind, 0), max(a))
        if len(a) == len(b):
            over = max(y - x for x, y in zip(a, b))
        else:
            over = max(b) - max(a)
        if over > 0:
            bad.append((over, kind, jp, k, max(a), max(b)))

    bad.sort(reverse=True)
    print('갈래별 원문 최대 줄 길이(칸):',
          ', '.join('%s %d' % (k, v) for k, v in sorted(mx.items())))
    print('\n원문보다 긴 줄이 있는 항목 %d개' % len(bad))
    for over, kind, jp, k, a, b in bad[:40]:
        print('  +%-2d %-8s %2d→%2d  %s' % (over, kind, a, b, jp[:34]))
        print('           %s' % k[:52])
    if len(bad) > 40:
        print('  … 외 %d개' % (len(bad) - 40))
    return bad


if __name__ == '__main__':
    main()

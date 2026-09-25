# -*- coding: utf-8 -*-
"""MENUBK 읽을거리(창 17칸 × 7줄)를 창 안에 넣는다.

  python tools/reflow_menubk.py                 검사만
  python tools/reflow_menubk.py --out <파일>     수정표로 뽑기

★창 규격은 실측이다 — 엔진이 **17칸에서 문자 단위로 강제 줄바꿈**하고
  **7줄을 넘는 줄은 사라진다**(스샷과 줄 단위로 일치 확인).

1단계 = «줄바꿈만 다시 흘리기». 원문 줄바꿈을 그대로 둔 탓에 줄 끝이 낭비돼
        11줄이 되던 것이, 낱말 경계로 다시 흘리면 7줄에 들어가기도 한다.
        글자를 안 건드리므로 뜻이 안 바뀐다 — **줄이기 전에 이것부터**.
2단계 = 그래도 넘치는 것만 손으로 줄인다(`--out` 에 안 담기고 목록에 뜬다).
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

NL = chr(92) + 'n'
TOK = re.compile(r'<!?[0-9A-Fa-f]{2}>|(.)', re.S)
WIDTH, HEIGHT = 17, 7


def cells(s):
    return sum(1 for m in TOK.finditer(s) if m.group(1))


def wrapped(text):
    return sum(max(1, -(-cells(s) // WIDTH)) for s in text.split(NL))


def reflow(text):
    """낱말 경계로 다시 흘린다. 빈 줄(문단 나눔)은 그대로 지킨다."""
    out = []
    for para in text.split(NL + NL):
        words = [w for w in para.replace(NL, ' ').split(' ') if w != '']
        lines, cur = [], ''
        for w in words:
            if cells(w) > WIDTH:
                return None
            cand = w if not cur else cur + ' ' + w
            if cells(cand) <= WIDTH:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        out.append(NL.join(lines))
    return (NL + NL).join(out)


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
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 6:
                units.append(p)
    mods = collections.defaultdict(set)
    with open('work/trans/places.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 7:
                mods[p[0]].add(p[2])

    fixed, still = [], []
    for r in units:
        if 'MENUBK' not in mods.get(r[0], ()):
            continue
        k = ko.get(r[5])
        if not k or k == r[5] or wrapped(k) <= HEIGHT:
            continue
        f2 = reflow(k)
        if f2 and wrapped(f2) <= HEIGHT:
            fixed.append((r[5], f2))
            continue
        # ★낱말 경계로 접으면 줄 끝이 남아 손해다. 엔진이 어차피 **문자 단위**로
        #   접으므로, 명시적 줄바꿈을 빼면 정확히 17칸씩 꽉 찬다.
        #   낱말 중간에서 끊겨 보기엔 덜 곱지만, 지금은 뒷부분이 통째로
        #   «사라지는» 상태라 그게 낫다.
        flat = ' '.join(x for x in k.replace(NL, ' ').split(' ') if x)
        if wrapped(flat) <= HEIGHT:
            fixed.append((r[5], flat))
            continue
        need = cells(flat) - WIDTH * HEIGHT
        still.append((need, r[5], k, flat))

    print('흘리기만으로 해결 %d건 / 손으로 줄여야 %d건' % (len(fixed), len(still)))
    if '--out' in sys.argv:
        p = sys.argv[sys.argv.index('--out') + 1]
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            for jp, v in fixed:
                f.write('%s\t%s\n' % (jp, v))
        print('→ %s (원문↦새 번역)' % p)
    if '--list' in sys.argv:
        for need, jp, k, f2 in sorted(still, reverse=True):
            print('  %+3d칸 초과 | %s' % (need, (f2 or k)[:100]))


if __name__ == '__main__':
    main()

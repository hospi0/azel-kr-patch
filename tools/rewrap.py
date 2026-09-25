# -*- coding: utf-8 -*-
"""고정창 텍스트의 «줄바꿈만» 다시 잡아 칸 초과를 푼다.

  python tools/rewrap.py            검사만
  python tools/rewrap.py --out work/over_wrap.tsv   수정표로 뽑기

★글자를 줄이는 게 아니라 **줄을 다시 나누는 것**뿐이다. 뜻이 안 바뀌므로
  손으로 줄이기 전에 이것부터 돌린다.

제약 두 가지를 **동시에** 만족해야 한다.
    ① 각 줄 ≤ 원문 최대 줄 폭   (창 가로 폭)
    ② 줄 수 ≤ 원문 줄 수        (창 세로 높이 — 넘치면 아래가 잘린다)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

NL = chr(92) + 'n'
# 제어코드·생바이트는 0칸. 나눌 때 앞 낱말에 붙여 둔다.
TOK = re.compile(r'<!?[0-9A-Fa-f]{2}>|(.)', re.S)


def cells(s):
    return sum(1 for m in TOK.finditer(s) if m.group(1))


def wrap(text, width, maxlines):
    """공백 기준 그리디 배치. 실패하면 None."""
    words = []
    for seg in text.split(NL):
        words += [w for w in seg.split(' ') if w != '']
    lines, cur = [], ''
    for w in words:
        if cells(w) > width:
            return None                    # 낱말 하나가 폭보다 길다 → 손으로
        cand = w if not cur else cur + ' ' + w
        if cells(cand) <= width:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > maxlines:
        return None
    return NL.join(lines)


def main():
    rows = [l.rstrip('\n').split('\t')
            for l in open('work/over_snap.tsv', encoding='utf-8')][1:]
    ok, fail = [], []
    for r in rows:
        if len(r) < 6:
            continue
        idx, kind, lim, over, jp, ko = r[0], r[1], int(r[2]), r[3], r[4], r[5]
        maxlines = len(jp.split(NL))
        w = wrap(ko, lim, maxlines)
        if w is None or max(cells(s) for s in w.split(NL)) > lim:
            fail.append((idx, kind, lim, jp, ko))
        else:
            ok.append((idx, w))
    print('리랩으로 풀림 %d건 / 손으로 줄여야 %d건' % (len(ok), len(fail)))
    if '--out' in sys.argv:
        p = sys.argv[sys.argv.index('--out') + 1]
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            for i, w in ok:
                f.write('%s\t%s\n' % (i, w))
        print('→ %s' % p)
    if '--fails' in sys.argv:
        for idx, kind, lim, jp, ko in fail[:40]:
            print('  #%s %-5s 상한%-3d %s' % (idx, kind, lim, ko[:70]))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""번역문에서 «마침표·쉼표 뒤 공백»을 없앤다.

  python tools/strip_space.py work/trans/kr [work/fix1.tsv ...]

공백 글리프는 **2바이트**를 먹는다(기본 폰트 index 1). 문장부호 뒤 공백을
없애는 것만으로 예산이 꽤 풀린다. 원문 `jp` 열은 건드리지 않는다 — 키니까.
"""
import os
import sys

PAIRS = [(', ', ','), ('. ', '.'), ('、 ', '、'), ('。 ', '。')]


def fix(s):
    for a, b in PAIRS:
        while a in s:
            s = s.replace(a, b)
    return s


def do_tsv(path, kocol):
    with open(path, encoding='utf-8') as f:
        lines = f.read().split('\n')
    out = []
    n = 0
    for i, line in enumerate(lines):
        if not line:
            out.append(line)
            continue
        r = line.split('\t')
        if len(r) > kocol and (i > 0 or kocol != 6):
            new = fix(r[kocol])
            if new != r[kocol]:
                n += 1
                r[kocol] = new
        out.append('\t'.join(r))
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(out))
    return n


def main():
    total = 0
    for a in sys.argv[1:]:
        if os.path.isdir(a):
            for fn in sorted(os.listdir(a)):
                if fn.endswith('.tsv'):
                    total += do_tsv(os.path.join(a, fn), 6)
        else:
            total += do_tsv(a, 1)
    print('공백 제거 %d행' % total)


if __name__ == '__main__':
    main()

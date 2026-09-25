# -*- coding: utf-8 -*-
"""번역문의 개행(`\\n`) 개수를 원문과 맞춘다.

  python tools/fix_newlines.py work/trans/kr

개행은 화면 줄바꿈이라 개수가 다르면 조판이 어긋난다. 손으로 세면 계속 틀리므로
**가장 긴 줄의 공백 하나를 개행으로 바꿔** 기계적으로 채운다(줄이 남으면 반대로
개행 하나를 공백으로 되돌린다). 바이트 수는 그대로다(공백 2B → 개행 1B 라
오히려 줄어든다).
"""
import os
import sys

BS = chr(92)
NL = BS + 'n'


def adjust(ko, want):
    parts = ko.split(NL)
    while len(parts) - 1 < want:
        i = max(range(len(parts)), key=lambda k: len(parts[k]))
        s = parts[i]
        cut = s.rfind(' ', 0, len(s) // 2 + len(s) // 4)
        if cut < 0:
            cut = s.rfind(' ')
        if cut < 0:
            return None
        parts[i:i + 1] = [s[:cut], s[cut + 1:]]
    while len(parts) - 1 > want:
        i = min(range(len(parts) - 1),
                key=lambda k: len(parts[k]) + len(parts[k + 1]))
        parts[i:i + 2] = [parts[i] + ' ' + parts[i + 1]]
    return NL.join(parts)


def main():
    krdir = sys.argv[1] if len(sys.argv) > 1 else 'work/trans/kr'
    n = 0
    for fn in sorted(os.listdir(krdir)):
        if not fn.endswith('.tsv'):
            continue
        path = os.path.join(krdir, fn)
        with open(path, encoding='utf-8') as f:
            lines = f.read().split('\n')
        out = []
        for i, line in enumerate(lines):
            if i == 0 or not line:
                out.append(line)
                continue
            r = line.split('\t')
            if len(r) >= 7 and r[6] and r[6] != r[5]:
                want = r[5].count(NL)
                if r[6].count(NL) != want:
                    new = adjust(r[6], want)
                    if new is not None:
                        r[6] = new
                        n += 1
            out.append('\t'.join(r))
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write('\n'.join(out))
    print('개행 수를 맞춘 행 %d개' % n)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""번역 단위를 갈래별 폴더에 30 KB 단위로 쪼개 놓는다 (번역 작업용).

  python tools/split_trans.py work/trans [갈래 ...]   # 기본: dialog narration

산출:
  work/trans/<갈래>/<갈래>_001.tsv …   각 파일 30 KB 이하
  열은 `jp` 와 **빈 `ko`** 두 개뿐이다 — 채워 넣기만 하면 된다.

★키는 «원문 텍스트»다. `units.tsv` 를 다시 만들면 id 가 밀리므로 id 를 키로 쓰면
  번역이 통째로 엉뚱한 자리에 붙는다(실제로 `MENUBK.BIN` 을 넣다가 겪었다).
  빌더(`build_kr.py`)도 원문으로 맞춘다.
"""
import os
import sys

LIMIT = 30 * 1024
DEFAULT = ['dialog', 'narration']


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else 'work/trans'
    kinds = sys.argv[2:] or DEFAULT

    rows = []
    with open(os.path.join(root, 'units.tsv'), encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 6:
                rows.append((p[1], p[3], p[5]))     # kind, budget, jp

    for kind in kinds:
        sel = [r for r in rows if r[0] == kind]
        d = os.path.join(root, kind)
        os.makedirs(d, exist_ok=True)
        for old in os.listdir(d):
            if old.endswith('.tsv'):
                os.remove(os.path.join(d, old))

        head = 'jp\tko\n'
        n = 1
        buf = [head]
        size = len(head.encode('utf-8'))
        made = []

        def flush():
            path = os.path.join(d, '%s_%03d.tsv' % (kind, n))
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.writelines(buf)
            made.append((path, size, len(buf) - 1))

        for _, budget, jp in sel:
            line = '%s\t\n' % jp
            b = len(line.encode('utf-8'))
            if size + b > LIMIT and len(buf) > 1:
                flush()
                n += 1
                buf = [head]
                size = len(head.encode('utf-8'))
            buf.append(line)
            size += b
        if len(buf) > 1:
            flush()

        print('%-10s %5d단위 → %d파일 (%s)'
              % (kind, len(sel), len(made), d))
        for path, sz, cnt in made:
            print('   %-28s %6.1f KB  %4d줄' % (os.path.basename(path),
                                                sz / 1024.0, cnt))


if __name__ == '__main__':
    main()

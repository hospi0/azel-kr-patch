# -*- coding: utf-8 -*-
"""TSV 를 헤더를 유지한 채 크기 단위로 쪼갠다.

  python tools/split_tsv.py <입력.tsv> [출력폴더] [KB]

  예) python tools/split_tsv.py work/trans/units.tsv          # 30 KB 씩
      python tools/split_tsv.py work/trans/places.tsv work/trans/places 30

한 줄이 잘리는 일이 없도록 줄 단위로만 나누고, 조각마다 첫 줄에 원본 헤더를 넣는다.
"""
import os
import sys


def split(path, outdir=None, kb=30):
    limit = kb * 1024
    name = os.path.splitext(os.path.basename(path))[0]
    outdir = outdir or os.path.join(os.path.dirname(path), name)
    os.makedirs(outdir, exist_ok=True)
    for old in os.listdir(outdir):
        if old.startswith(name + '_') and old.endswith('.tsv'):
            os.remove(os.path.join(outdir, old))

    with open(path, encoding='utf-8') as f:
        head = f.readline()
        lines = f.readlines()

    n = 1
    buf = [head]
    size = len(head.encode('utf-8'))
    made = []

    def flush():
        p = os.path.join(outdir, '%s_%03d.tsv' % (name, n))
        with open(p, 'w', encoding='utf-8', newline='') as g:
            g.writelines(buf)
        made.append((os.path.basename(p), size, len(buf) - 1))

    for line in lines:
        b = len(line.encode('utf-8'))
        if size + b > limit and len(buf) > 1:
            flush()
            n += 1
            buf = [head]
            size = len(head.encode('utf-8'))
        buf.append(line)
        size += b
    if len(buf) > 1:
        flush()

    print('%s → %d파일 (%s)' % (os.path.basename(path), len(made), outdir))
    for nm, sz, cnt in made:
        print('   %-24s %6.1f KB %5d줄' % (nm, sz / 1024.0, cnt))
    return made


if __name__ == '__main__':
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    kb = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    split(src, out, kb)

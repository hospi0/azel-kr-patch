# -*- coding: utf-8 -*-
"""아이템 이름표를 번역용으로 뽑는다.

  python tools/extract_items.py [work/uniq/COMMON.DAT] [work/trans/items.tsv]

이름표는 `COMMON.DAT` 안에 **반각 JIS X0201** 로 널종단·4바이트 정렬로 놓여 있다.
자리를 넘길 수 없으므로 `budget` = 원문 바이트 수(종단 포함).
★반각은 **1바이트/글자**다 — 전각 본문(2바이트)보다 자리가 훨씬 빡빡하다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import halfwidth as hw

START, END = 0x00C8D8, 0x00CF90


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'work/uniq/COMMON.DAT'
    out = sys.argv[2] if len(sys.argv) > 2 else 'work/trans/items.tsv'
    data = open(src, 'rb').read()

    rows = []
    p = START
    while p < END:
        if data[p] == 0:
            p += 1
            continue
        s, nxt = hw.read_name(data, p)
        if s is None or len(s) < 1:
            p += 1
            continue
        # 다음 문자열까지의 «자리» = 4바이트 정렬 다음 칸까지
        room = nxt - p                      # 종단 포함
        pad = 0
        q = nxt
        while q < END and data[q] == 0:
            pad += 1
            q += 1
        rows.append((p, s, room, room + pad))
        p = q

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='') as f:
        f.write('off\tjp\tbytes\troom\tko\n')
        for off, s, room, tot in rows:
            f.write('%06X\t%s\t%d\t%d\t\n' % (off, s, room, tot))

    print('아이템 이름 %d개 → %s' % (len(rows), out))
    print('자리(패딩 포함) 분포: 최소 %d / 최대 %d / 평균 %.1f'
          % (min(r[3] for r in rows), max(r[3] for r in rows),
             sum(r[3] for r in rows) / len(rows)))
    print('\n표본:')
    for off, s, room, tot in rows[:12]:
        print('   %06X  %-14s 바이트%2d 자리%2d' % (off, s, room, tot))


if __name__ == '__main__':
    main()

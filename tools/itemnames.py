# -*- coding: utf-8 -*-
"""아이템 «이름표» — 반각 JIS X0201 로 저장된 구간을 뽑는다.

  python tools/itemnames.py [work/uniq/COMMON.DAT]

★★이 표는 **글리프 인덱스 스트림이 아니다**. 반각 가타카나(JIS X0201) 1바이트
  코드로 저장돼 있고, 렌더러가 그때그때 글리프 index 로 바꿔 그린다
  (ｵ 0xB5 → index 87, ﾌ+ﾞ → ブ 153 처럼 탁점도 합친다).
  그래서 «글리프 인덱스로만» 훑던 추출기가 통째로 놓쳤다 — 실기 화면에서
  아이템 이름이 깨져 보여서야 존재를 알았다.
"""
import os
import sys

HALF = ('｡｢｣､･ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ'
        'ﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ')
BASE = 0xA1                     # ｡ 부터


def ch(b):
    if 0x20 <= b < 0x7F:
        return chr(b)
    i = b - BASE
    if 0 <= i < len(HALF):
        return HALF[i]
    return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'work/uniq/COMMON.DAT'
    data = open(path, 'rb').read()

    runs = []
    cur, start = [], None
    i = 0
    while i < len(data):
        c = ch(data[i])
        if c is not None:
            if start is None:
                start = i
            cur.append(c)
            i += 1
            continue
        if data[i] == 0 and cur:
            if len(cur) >= 2:
                runs.append((start, ''.join(cur)))
            cur, start = [], None
            i += 1
            continue
        cur, start = [], None
        i += 1
    print('반각 문자열 %d개' % len(runs))

    # 촘촘히 이어진 덩어리만 = 이름표
    groups = []
    g = []
    prev_end = None
    for off, s in runs:
        end = off + len(s) + 1
        if prev_end is not None and off - prev_end > 24:
            if len(g) >= 8:
                groups.append(g)
            g = []
        g.append((off, s))
        prev_end = end
    if len(g) >= 8:
        groups.append(g)

    print('덩어리 %d개' % len(groups))
    for g in groups:
        print('\n=== %06X..%06X  %d개' % (g[0][0], g[-1][0], len(g)))
        for off, s in g:
            print('   %06X (%2d) %s' % (off, len(s), s))


if __name__ == '__main__':
    main()

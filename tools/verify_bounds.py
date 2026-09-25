# -*- coding: utf-8 -*-
"""«널 종단 경계»가 원본과 패치에서 똑같은지 파일 전체로 검사한다 (2026-08-15).

왜
  `verify_disc.py`(되읽기)·`verify_ctrl.py`(제어코드)는 **우리가 신고한 자리**만 본다.
  패딩이 한 바이트라도 넘치거나 종단자가 밀리면 **다음 항목이 통째로 사라진다**
  ([[feedback_budget_eats_next_string]]). 그 결과는 「글자가 이상하다」가 아니라
  스크립트·메뉴 파서가 항목을 잘못 세어 **화면이 안 뜨거나 크래시**다.

판정
  파일 전체에서 `00` 위치 목록을 뽑아 원본과 패치를 대조한다. 텍스트는 원문 길이를
  지키므로 **경계는 한 곳도 달라지면 안 된다**.

사용: python verify_bounds.py <원본Track1> <패치Track1> [모듈…]
"""
import os, sys, csv, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from iso9660 import Iso

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES = os.path.join(REPO, 'work', 'trans', 'places.tsv')
SRC_FILE = {'MOVIE': 'MOVIE.DAT', 'MENUBK': 'MENUBK.BIN', 'COMMON': 'COMMON.DAT'}


def out(m):
    sys.stdout.buffer.write((str(m) + '\n').encode('utf-8', 'replace'))


def main():
    io, ip = Iso(sys.argv[1]), Iso(sys.argv[2])
    only = set(sys.argv[3:])
    mo = {p.split('/')[-1]: (l, s) for p, l, s in io.walk()}
    mp = {p.split('/')[-1]: (l, s) for p, l, s in ip.walk()}
    mods = sorted({r['module'] for r in
                   csv.DictReader(open(PLACES, encoding='utf-8'), delimiter='\t')})
    total = 0
    for mod in mods:
        if only and mod not in only:
            continue
        fn = SRC_FILE.get(mod, mod + '.PRG')
        if fn not in mo or fn not in mp:
            continue
        a = io.read(*mo[fn])
        b = ip.read(*mp[fn])
        if a == b:
            continue
        na = [i for i, c in enumerate(a) if c == 0]
        nb = [i for i, c in enumerate(b) if c == 0]
        if na == nb:
            continue
        sa, sb = set(na), set(nb)
        lost = sorted(sa - sb)      # 원본에 있던 종단자가 사라짐 = 다음 항목을 먹었다
        added = sorted(sb - sa)     # 없던 자리에 00 = 항목이 잘렸다
        total += len(lost) + len(added)
        out(f'{mod}: 사라진 종단 {len(lost)}  새 종단 {len(added)}')
        for x in lost[:12]:
            out(f'   ✖사라짐 {x:#08x}  원본 {a[max(0,x-10):x+6].hex(" ")}')
            out(f'                패치 {b[max(0,x-10):x+6].hex(" ")}')
        for x in added[:12]:
            out(f'   ＋새 종단 {x:#08x}  원본 {a[max(0,x-10):x+6].hex(" ")}')
            out(f'                패치 {b[max(0,x-10):x+6].hex(" ")}')
    out(f'\n경계 어긋남 {total}건 ' + ('✅' if not total else '❌'))


if __name__ == '__main__':
    main()

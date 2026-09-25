# -*- coding: utf-8 -*-
"""«종단자 위치»가 원본과 패치에서 같은지, 자리마다 토큰을 따라가며 검사한다 (2026-08-15).

왜
  앞 문자열의 패딩이 한 토큰이라도 넘치면 **뒤의 짧은 항목이 통째로 사라진다**
  ([[feedback_budget_eats_next_string]]). 그 결과는 글자 깨짐이 아니라 «메뉴가 안 뜸 /
  스크립트 폭주»다. 되읽기 검증은 우리가 쓴 바이트만 보므로 원리상 못 잡는다.

⛔순진한 `00` 스캔은 안 된다 — `81 00`(index 256) 처럼 **2바이트 토큰의 뒷바이트**가
  0x00 인 경우가 흔해 거짓 양성이 쏟아진다([[feedback_terra_7e_ba_codec_bug]] 와 같은 함정).
  반드시 문자열 시작부터 토큰을 따라가 «리드 위치의 0x00»만 종단자로 센다.

사용: python verify_term.py <원본Track1> <패치Track1> [모듈…]
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


def term_at(d, off, limit=512):
    """off 부터 토큰을 따라가 종단자(리드 위치의 0x00) 오프셋을 돌려준다."""
    i = off
    end = min(off + limit, len(d) - 1)
    while i < end:
        b = d[i]
        if b == 0:
            return i
        i += 2 if b >= 0x80 else 1
    return None


def main():
    io, ip = Iso(sys.argv[1]), Iso(sys.argv[2])
    only = set(sys.argv[3:])
    mo = {p.split('/')[-1]: (l, s) for p, l, s in io.walk()}
    mp = {p.split('/')[-1]: (l, s) for p, l, s in ip.walk()}

    by = collections.defaultdict(list)
    for r in csv.DictReader(open(PLACES, encoding='utf-8'), delimiter='\t'):
        by[r['module']].append((int(r['offset'], 16), int(r['budget']), r['kind'], r['id']))

    cache = {}
    bad = 0
    for mod, lst in sorted(by.items()):
        if only and mod not in only:
            continue
        fn = SRC_FILE.get(mod, mod + '.PRG')
        if fn not in mo or fn not in mp:
            continue
        if mod not in cache:
            cache[mod] = (io.read(*mo[fn]), ip.read(*mp[fn]))
        a, b = cache[mod]
        if a == b:
            continue
        for off, bud, kind, uid in sorted(lst):
            ta, tb = term_at(a, off), term_at(b, off)
            if ta is None or tb is None or ta == tb:
                continue
            bad += 1
            out(f'{mod} {off:#08x} id={uid} {kind} bud={bud}: '
                f'종단 {ta:#x} → {tb:#x} ({tb-ta:+d}B)')
            out(f'   원본 {a[off:ta+1].hex(" ")}')
            out(f'   패치 {b[off:tb+1].hex(" ")}')
            # 먹힌 자리에 원본이 뭘 갖고 있었나
            if tb > ta:
                out(f'   ✖먹힌 원본 {a[ta+1:tb+1].hex(" ")}')
    out(f'\n종단 위치 어긋남 {bad}건 ' + ('✅' if not bad else '❌'))


if __name__ == '__main__':
    main()

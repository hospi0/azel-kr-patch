# -*- coding: utf-8 -*-
"""«토큰 폭»이 원문과 같은지 검사한다 (2026-08-15).

이 게임의 문자열은 [2바이트 글리프 토큰 | 1바이트 글리프 토큰(0x20~0x7F) |
1바이트 제어코드(<0x20)] 가 섞인다. **원문이 1바이트로 쓰던 글자를 2바이트로
쓰면 그 뒤가 통째로 한 바이트씩 밀린다** — 되읽기 검증은 «우리가 의도한 대로
썼는가»만 보므로 이걸 못 잡는다. 원문 대비로만 잡힌다.

실제 사고(2026-08-15): 「패딩을 줄이려 전부 2바이트로 쓴다」는 정책이
`)`(원본 1바이트 `3C`)까지 `80 3C` 로 바꿔, 지명 상자가
「카라반」→「가·깨짐·라·반」 으로 깨졌다.

판정 = **원문이 1바이트 글리프 토큰을 한 번도 안 쓰는 자리에 우리가 넣었는가.**
       (토큰 «수»는 번역이라 당연히 달라지므로 비교하지 않는다 —
        그걸로 재면 7,371곳이 걸려 쓸모가 없다.)

사용: python verify_tokwidth.py <원본Track1> <패치Track1>
"""
import os, sys, csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from iso9660 import Iso

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES = os.path.join(REPO, 'work', 'trans', 'places.tsv')
SRC_FILE = {'MOVIE': 'MOVIE.DAT', 'MENUBK': 'MENUBK.BIN', 'COMMON': 'COMMON.DAT'}


def one_byte_glyphs(d, off, bud):
    """(1바이트 글리프 토큰 개수, 슬롯 안에서 정합하게 끝났는가)."""
    n, i, end = 0, off, off + bud
    while i < end:
        v = d[i]
        if v >= 0x80:
            if i + 1 >= end:
                return n, False
            i += 2
        elif v == 0:
            return n, True
        elif v < 0x20:          # 제어코드
            i += 1
        else:                   # 1바이트 «글리프» 토큰
            n += 1
            i += 1
    return n, False


def main():
    io, ip = Iso(sys.argv[1]), Iso(sys.argv[2])
    mo = {p.split('/')[-1]: (l, s) for p, l, s in io.walk()}
    mp = {p.split('/')[-1]: (l, s) for p, l, s in ip.walk()}
    co, cp = {}, {}

    def get(iso, mm, cache, fn):
        if fn not in cache:
            cache[fn] = iso.read(*mm[fn]) if fn in mm else None
        return cache[fn]

    rows = list(csv.DictReader(open(PLACES, encoding='utf-8'), delimiter='\t'))
    checked = skipped = 0
    bad = []
    for r in rows:
        fn = SRC_FILE.get(r['src'], r['module'] + '.PRG')
        o, p = get(io, mo, co, fn), get(ip, mp, cp, fn)
        if o is None or p is None:
            continue
        off, bud = int(r['offset'], 16), int(r['budget'])
        if off + bud > len(o):
            continue
        so, ok = one_byte_glyphs(o, off, bud)
        if not ok:                      # 원문이 슬롯 안에서 안 끝나면 판정 불가
            skipped += 1
            continue
        checked += 1
        sp, _ = one_byte_glyphs(p, off, bud)
        if so == 0 and sp > 0:
            bad.append((fn, r['offset'], bud, so, sp))

    print('검사 %d곳 / 판정불가 %d곳' % (checked, skipped))
    print('원문엔 1바이트 글리프가 없는데 우리가 넣은 곳: %d곳 %s'
          % (len(bad), '✅' if not bad else '❌'))
    import collections
    c = collections.Counter(x[0] for x in bad)
    for k, v in c.most_common(15):
        print('   %-16s %d곳' % (k, v))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

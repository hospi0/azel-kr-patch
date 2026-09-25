# -*- coding: utf-8 -*-
"""«문자열이 한 번도 안 쓰는 장면 FNT 칸» = 코드가 직접 그리는 글리프 → 예약 (2026-08-15).

경위(실기): 상점 가격의 화폐 단위 `dn` 이 「감」으로 나왔다.
`ITEM.FNT` 의 글리프 0·1·2 는 `Ln` `Kn` `Dn` — **단위 합자**인데, 어느 문자열도
이 칸을 가리키지 않는다. 코드가 index 를 직접 써서 그리기 때문이다.
그래서 `fnt_reserved.py`(원본 문자열에 남은 토큰을 예약)로는 **원리상 안 잡힌다**.

판정
  그 FNT 를 쓰는 자리들의 **원본 바이트**를 훑어 쓰인 index 집합을 만들고,
  FNT 글리프 수 안에서 **한 번도 안 쓰인 칸**을 예약한다.
  ITEM.FNT 는 299칸 중 정확히 0·1·2 만 남았다 — 원인과 정확히 일치한다.

과잉 예약은 «안전한 실패»다(칸이 모자라면 빌드가 멈출 뿐), 반대는 화면 파손이다.

  python fnt_code_slots.py <무수정 Track1> [--merge]   → work/fnt_reserved.tsv 에 합침
"""
import os, sys, csv, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from iso9660 import Iso

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES = os.path.join(REPO, 'work', 'trans', 'places.tsv')
RESERVED = os.path.join(REPO, 'work', 'fnt_reserved.tsv')
SRC_FILE = {'MOVIE': 'MOVIE.DAT', 'MENUBK': 'MENUBK.BIN', 'COMMON': 'COMMON.DAT'}


def out(m):
    sys.stdout.buffer.write((str(m) + '\n').encode('utf-8', 'replace'))


def main():
    iso = Iso(sys.argv[1])
    merge = '--merge' in sys.argv
    files = {p.split('/')[-1]: (l, s) for p, l, s in iso.walk()}
    cache = {}

    def data(fn):
        if fn not in cache:
            if fn not in files:
                cache[fn] = None
            else:
                l, s = files[fn]
                cache[fn] = iso.read(l, s)
        return cache[fn]

    # fnt → [(module, offset, budget)]
    by = collections.defaultdict(list)
    for r in csv.DictReader(open(PLACES, encoding='utf-8'), delimiter='\t'):
        by[r['fnt']].append((r['module'], int(r['offset'], 16), int(r['budget'])))

    # 이미 예약된 칸은 «쓰이는 것»으로 친다(어차피 재활용 금지라 결과가 같다).
    already = collections.defaultdict(set)
    if os.path.exists(RESERVED):
        for r in csv.DictReader(open(RESERVED, encoding='utf-8'), delimiter='\t'):
            already[r['fnt']].add(int(r['index']))

    rows = []
    for fnt, lst in sorted(by.items()):
        fd = data(fnt + '.FNT')
        if not fd or len(fd) < 2:
            continue
        n = int.from_bytes(fd[:2], 'big')          # BE16 글리프 수
        if not (0 < n < 4096):
            continue
        used = set()
        for mod, off, bud in lst:
            d = data(SRC_FILE.get(mod, mod + '.PRG'))
            if not d:
                continue
            i, end = off, min(off + bud, len(d) - 1)
            while i < end:
                b = d[i]
                if b >= 0x80:
                    used.add(((b & 0x7F) << 8) | d[i + 1])
                    i += 2
                else:
                    i += 1
        free = [256 + k for k in range(n) if (256 + k) not in used
                and (256 + k) not in already[fnt]]
        # ⛔오탐 걸러내기: 진짜 «코드 전용» 칸은 극소수다. 절반 넘게 미사용으로 나오면
        # 그 FNT 는 자리 정보(offset 기준)가 우리와 다른 것이다 — 무비 자막(EVT*)이
        # MOVIE.DAT 안 오프셋을 쓰는 탓에 전 칸이 미사용으로 잡혔다.
        if len(free) > n // 2:
            out(f'{fnt}: {n}칸 중 {len(free)}칸 미사용 — 자리 기준 불일치로 보고 건너뜀')
            continue
        if free:
            rows += [(fnt, k) for k in free]
            out(f'{fnt}: {n}칸 중 문자열 미사용 {len(free)}칸 → '
                + ' '.join(str(k - 256) for k in free[:20])
                + (' …' if len(free) > 20 else ''))

    out(f'\n코드 전용 후보 {len(rows)}칸')
    if not merge:
        out('(합치려면 --merge)')
        return
    old = []
    if os.path.exists(RESERVED):
        old = [(r['fnt'], int(r['index']))
               for r in csv.DictReader(open(RESERVED, encoding='utf-8'), delimiter='\t')]
    allr = sorted(set(old) | set(rows))
    with open(RESERVED, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t')
        w.writerow(['fnt', 'index'])
        w.writerows(allr)
    out(f'{RESERVED} — {len(old)} → {len(allr)}칸')


if __name__ == '__main__':
    main()

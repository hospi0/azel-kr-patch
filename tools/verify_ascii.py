# -*- coding: utf-8 -*-
"""«원본이 순수 ASCII 문자열인 자리»를 우리가 덮지 않았는지 검사한다 (2026-08-15).

경위(실기): 도감 몬스터 감상 화면 오른쪽에 `)))))` 가 4줄 떴다. 원본은 그 자리가
완전히 비어 있다. 원인은 `MENUEN.PRG 0x28A8` — 원본이 **ASCII 공백 5칸**
(`20 20 20 20 20 00`)인데, 추출기가 이걸 글리프 토큰으로 읽어 `ななななな` 라는
«번역 단위»를 만들었고(1바이트 토큰 0x20 = 글리프 index 32 = な), 빌더가 그 자리에
1바이트 공백 글리프 index `0x29` 를 다섯 개 써 넣었다. 이 자리를 소비하는 쪽은
글리프 렌더러가 아니라 **printf 계열 ASCII 경로**라, 0x29 를 그대로 `)` 로 찍었다.
바로 옆에 `"R" "G" "B" "L" ":%3d"` 가 있는 것으로 ASCII 표임이 확정된다.

★교훈: 「글리프 토큰으로 디코드된다」는 「글리프 토큰이다」가 아니다.
  0x20~0x7E 는 1바이트 글리프 토큰 범위와 ASCII 가 통째로 겹친다.

판정 = 원본 슬롯의 본문(널 제거)이 **전부 0x20~0x7E** 인데 패치가 그 자리를
       바꿨으면 실패. 해당 자리는 `build_kr.BLOCKED_PLACES` 에 넣어 차단한다.

사용: python verify_ascii.py <원본Track1> <패치Track1>
"""
import os, sys, csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from iso9660 import Iso

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES = os.path.join(REPO, 'work', 'trans', 'places.tsv')
UNITS = os.path.join(REPO, 'work', 'trans', 'units.tsv')
SRC_FILE = {'MOVIE': 'MOVIE.DAT', 'MENUBK': 'MENUBK.BIN', 'COMMON': 'COMMON.DAT'}
MIN_LEN = 2                 # 1글자짜리는 판정 불가(노이즈)


def main():
    io, ip = Iso(sys.argv[1]), Iso(sys.argv[2])
    mo = {p.split('/')[-1]: (l, s) for p, l, s in io.walk()}
    mp = {p.split('/')[-1]: (l, s) for p, l, s in ip.walk()}
    co, cp = {}, {}

    def get(iso, mm, cache, fn):
        if fn not in cache:
            cache[fn] = iso.read(*mm[fn]) if fn in mm else None
        return cache[fn]

    jp_of = {r['id']: r['jp'] for r in csv.DictReader(
        open(UNITS, encoding='utf-8'), delimiter='\t')}
    bad = []
    for r in csv.DictReader(open(PLACES, encoding='utf-8'), delimiter='\t'):
        fn = SRC_FILE.get(r['src'], r['module'] + '.PRG')
        o, p = get(io, mo, co, fn), get(ip, mp, cp, fn)
        if o is None or p is None:
            continue
        off, bud = int(r['offset'], 16), int(r['budget'])
        if off + bud > len(o):
            continue
        so = o[off:off + bud]
        if so == p[off:off + bud]:
            continue
        body = so.rstrip(b'\x00')
        if len(body) < MIN_LEN:
            continue
        if all(0x20 <= c < 0x7F for c in body):
            bad.append((fn, off, bud, body, p[off:off + bud].rstrip(b'\x00'),
                        jp_of.get(r['id'], '')))

    print('원본이 순수 ASCII인데 덮은 자리: %d곳 %s'
          % (len(bad), '✅' if not bad else '❌'))
    for fn, off, bud, so, sp, jp in bad:
        print('   %-14s 0x%06X bud=%-3d %-24r → %-24r  (추출 jp=%r)'
              % (fn, off, bud, so, sp, jp))
    if bad:
        print('   ⇒ build_kr.BLOCKED_PLACES 에 (모듈, 오프셋) 을 넣어 차단할 것')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

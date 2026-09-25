# -*- coding: utf-8 -*-
"""번역이 «제어코드·종단자»를 먹지 않았는지 원본↔패치본 바이트로 검사한다.

배경 (2026-08-14)
    이 게임의 문자열은 [2바이트 글리프 토큰 | 1바이트 글리프 토큰(0x20~0x7F) |
    1바이트 제어코드(<0x20, 0x00=종단)] 이 섞인 스트림이다. 번역문이 원문 길이에
    딱 맞춰 들어가므로, 자리가 모자라면 **제어코드가 조용히 빠질 수 있다**
    (실측: BTL_T0 전투 설명 4건에서 앞쪽 `06`(개행)이 사라져 설명과 계통 이름이
    한 줄에 붙었고, 한 건은 `SPIRITUAL계` 가 `SPIRITUA` 로 잘려 있었다).
    ★번역 품질 검수로는 안 잡힌다 — 화면에 나오는 «글자»는 멀쩡하기 때문이다.

★검출기 함정: places 의 offset 이 토큰 경계가 아닌 항목이 있다. 그대로 토큰화하면
  2바이트 토큰의 뒷바이트를 제어코드로 오독해 **거짓 양성**이 쏟아진다.
  → 원본을 off 부터 토큰화해 **정확히 마지막 바이트에서 NUL 로 끝나는 것만** 검사한다.

사용: python verify_ctrl.py <원본Track1> <패치Track1>
"""
import sys, os, csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from iso9660 import Iso

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES = os.path.join(REPO, 'work', 'trans', 'places.tsv')
SRC_FILE = {'MOVIE': 'MOVIE.DAT', 'MENUBK': 'MENUBK.BIN', 'COMMON': 'COMMON.DAT'}


def tokens(d, a, n):
    """[(종류, 값)] — 'G' 글리프, 'C' 제어코드. 예산 n 바이트 안에서만."""
    out, i, end = [], a, a + n
    while i < end:
        v = d[i]
        if v >= 0x80:
            if i + 1 >= end:
                return out, False
            out.append(('G', ((v & 0x7F) << 8) | d[i + 1]))
            i += 2
        elif v < 0x20:
            # ⛔0x20~0x7F 는 «1바이트 글리프 토큰»이지 제어코드가 아니다.
            #   여기서 갈래를 안 나누면 한글 1바이트 토큰이 전부 제어코드로 잡혀
            #   거짓 양성 9,352건이 쏟아진다(2026-08-14에 실제로 그랬다).
            out.append(('C', v))
            i += 1
            if v == 0:
                return out, (i == end)      # 마지막 바이트에서 끝나야 정합
        else:
            out.append(('G', v))
            i += 1
    return out, False


def main():
    orig, pat = sys.argv[1], sys.argv[2]
    io, ip = Iso(orig), Iso(pat)
    mo = {p.split('/')[-1]: (l, s) for p, l, s in io.walk()}
    mp = {p.split('/')[-1]: (l, s) for p, l, s in ip.walk()}
    co, cp = {}, {}

    def get(iso, mm, cache, name):
        if name not in cache:
            cache[name] = iso.read(*mm[name]) if name in mm else None
        return cache[name]

    rows = list(csv.DictReader(open(PLACES, encoding='utf-8'), delimiter='\t'))
    checked = skipped = absent = 0
    bad = []
    for r in rows:
        fn = SRC_FILE.get(r['src'], r['module'] + '.PRG')
        o = get(io, mo, co, fn)
        p = get(ip, mp, cp, fn)
        if o is None or p is None:
            absent += 1
            continue
        off, bud = int(r['offset'], 16), int(r['budget'])
        if off + bud > len(o):
            skipped += 1
            continue
        to, ok = tokens(o, off, bud)
        # ★두 번째 가드: 글리프 index 가 어떤 폰트보다도 크면 «토큰 경계가 어긋난 것»이다
        #   (가장 큰 폰트도 기본256+715=971). 예: `bd 80 1b 00` 을 앞에서부터 읽으면
        #   index 15744 가 나오는데, 이건 이 항목의 offset 이 토큰 중간을 가리킨다는 뜻.
        #   이 가드가 없으면 뒤따르는 `1b` 를 제어코드로 오독해 거짓 양성이 수십 건 난다.
        if not ok or any(k == 'G' and v > 1023 for k, v in to):
            skipped += 1
            continue
        checked += 1
        tp, okp = tokens(p, off, bud)
        a = [v for k, v in to if k == 'C']
        b = [v for k, v in tp if k == 'C']
        if a != b or not okp:
            bad.append((fn, r['offset'], bud, a, b, okp))

    print(f'검사 {checked:,}곳 / 판정불가 {skipped}곳 / 파일없음 {absent}곳')
    print(f'제어코드·종단자 불일치: {len(bad)}곳 ' + ('✅' if not bad else '❌'))
    for fn, off, bud, a, b, okp in bad[:40]:
        note = '' if okp else '  ⚠종단자 위치도 다름'
        print(f'   {fn:16s} 0x{off} bud={bud:<4d} 원본{a} → 패치{b}{note}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

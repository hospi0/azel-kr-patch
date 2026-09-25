# -*- coding: utf-8 -*-
"""디스크의 텍스트 분량을 잰다 (PRG 전수).

  python tools/census.py <추출디렉터리>        # 예: work/jp1

세션1 판은 토큰 문법만으로 구간을 긁어 **하한이자 노이즈 포함**이었다.
지금은 파이프라인이 셋으로 늘었다.

  regions.find   널 종단 문자열이 밀집한 «구간» 만 뽑는다
  strtab         구간을 문자열로 쪼갠다 (2바이트/1바이트 글리프 토큰 + 제어코드)
  slots          고정 슬롯 배열을 찾아 **꼬리 잔재를 걷어낸다**

그래서 나오는 «살아있는» 수치가 번역 대상 모집단에 훨씬 가깝다.
다만 아직 확정값은 아니다 — 남은 미해독 4% 대와 짝 FNT 미확정 모듈이 있다.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import fnt as fntmod
import regions
import slots
import strtab

# PRG ↔ 짝 FNT. 이름이 다른 것만 적는다.
# 이름으로 유도되지 않는 것은 «PRG 가 쓰는 최대 글리프 index + 1» 이 FNT 글리프 수와
# 정확히 맞는 것을 후보로 잡고, 실제로 렌더해 일본어가 되는지 확인해 확정했다.
PAIR = {
    'TWN_ZOAH': 'EVTZOAH', 'TWN_CAMP': 'EVTCAMP', 'TWN_CARA': 'EVTCARA',
    'TWN_SEEK': 'EVTSEEK', 'TWN_EXCA': 'EVTEXCA', 'TWN_RUIN': 'EVTRUIN',
    # 필요 229 ↔ FLD_T0 229 / 필요 39 ↔ WORLDMAP 39 / 필요 50 ↔ SAVE 50
    'FLD_C8': 'FLD_T0', 'WORLD': 'WORLDMAP', '1ST_READ': 'SAVE',
}
# 무비 이벤트 설명 모듈 12개가 EVEEXPL(185자) 하나를 공유한다.
# 내용은 전부 «(未完成・将来セリフ組み込み予定)» 가 붙은 개발용 플레이스홀더다.
for _m in ('TWN_E006', 'TWN_E011', 'TWN_E014', 'TWN_E021', 'TWN_E022', 'TWN_E057',
           'TWN_E059', 'TWN_E120', 'TWN_E121', 'TWN_E128', 'TWN_JIRI'):
    PAIR[_m] = 'EVEEXPL'


def pair_of(stem, fonts):
    """짝 FNT 이름. 못 찾으면 None."""
    if stem in PAIR and PAIR[stem] in fonts:
        return PAIR[stem]
    if stem in fonts:
        return stem
    # BTL_A3_2.PRG ↔ BTL_A32.FNT — 마지막 언더스코어를 뗀 이름
    i = stem.rfind('_')
    if i > 0:
        alt = stem[:i] + stem[i + 1:]
        if alt in fonts:
            return alt
    return None


def survey(path, nmax):
    data = open(path, 'rb').read()
    nstr = nch = live_n = live_ch = narr = nitem = nbad = 0
    steps = Counter()
    for a, b, _, _, _ in regions.find(data, nmax):
        tab, _ = strtab.parse_table(data, a, nmax, lenient=True)
        tab = [e for e in tab if e[0] < b]
        arrs = slots.find_slot_arrays(data, tab, a, b)
        live = slots.live_offsets(data, tab, a, b)
        narr += len(arrs)
        for st, step, n, _, _ in arrs:
            nitem += n
            steps[step] += n
        for o, raw, t in tab:
            if strtab.is_asset_name(raw):
                continue
            n = sum(1 for k, _ in t if k in ('g', 'g1'))
            nstr += 1
            nch += n
            if o in live:
                live_n += 1
                live_ch += n
                nbad += any(k == 'x' for k, _ in t)
    return nstr, nch, live_n, live_ch, narr, nitem, nbad, steps


def main():
    d = sys.argv[1]
    fonts = {f[:-4]: len(fntmod.parse(open(os.path.join(d, f), 'rb').read()))
             for f in os.listdir(d) if f.endswith('.FNT')}
    maxf = max(fonts.values())
    prgs = sorted(f for f in os.listdir(d) if f.endswith('.PRG'))

    print('%-14s %8s %7s %8s %7s %8s %6s  %s'
          % ('PRG', '문자열', '글자', '살아있음', '글자', '슬롯항목', '미해독', '짝 FNT'))
    tot = [0] * 7
    steps = Counter()
    for p in prgs:
        stem = p[:-4]
        f = pair_of(stem, fonts)
        nmax = 256 + (fonts[f] if f else maxf)
        r = survey(os.path.join(d, p), nmax)
        for i in range(7):
            tot[i] += r[i]
        steps += r[7]
        if r[0]:
            print('%-14s %8d %7d %8d %7d %8d %6d  %s'
                  % (p, r[0], r[1], r[2], r[3], r[5], r[6],
                     f if f else '(미확정 %d 가정)' % maxf))
    print('-' * 78)
    print('%-14s %8d %7d %8d %7d %8d %6d'
          % ('합계', tot[0], tot[1], tot[2], tot[3], tot[5], tot[6]))
    print('슬롯 크기 분포:', sorted(steps.items(), key=lambda x: -x[1])[:8])


if __name__ == '__main__':
    main()

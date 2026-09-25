# -*- coding: utf-8 -*-
"""고정 크기 «슬롯 배열» 검출 — 선택지 메뉴 데이터.

디스크1 `TWN_ZOAH.PRG` `0x22862..0x279C5` 구간에서 밝혀낸 구조다.

  * 선택지 메뉴 항목이 **고정 크기 슬롯**에 하나씩 들어 있다(주력 31 B, 그 밖에
    40·42·64·65·73·77 B). 항목 시작 오프셋이 정확히 슬롯 크기 간격으로 늘어선다.
  * 문자열은 슬롯보다 짧고, **남는 꼬리에는 이전 데이터가 그대로 남아 있다**.
    그래서 순차 파싱하면 죽은 바이트가 «미해독 문자열»로 보인다.
  * 근거: US 같은 자리가 `About the Empire / About the Dragon / …/ Quit` 선택지
    목록이고, JP 는 `帝国の噂 / ドラゴンの噂 / ゾアの街の噂 …/ 噂をやめる` 이다.

★한글화 함의: 이 항목들은 **슬롯 크기 제약**을 받는다. 31 B 슬롯이면 종단 포함
  31 B 안에 들어가야 하고, 2바이트 토큰만 쓰면 15글자다.

--------------------------------------------------------------------------------
검출은 **세 판정을 AND** 로 건다. 하나씩으로는 전부 부족하다.

  (1) 등간격      — 항목 시작이 정확히 같은 간격으로 늘어선다.
  (2) 꼬리 잔재    — 슬롯 내부(경계가 아닌 자리)에 걸린 조각이 둘 중 하나다.
                    (2a) **미해독 리드 바이트로 시작**한다 — `9B 00`, `B9 80 37…`
                         처럼 토큰 경계가 어긋난 조각. 그 자체로 유효한 문자열이
                         아니므로 죽은 바이트라는 직접 증거다.
                    (2b) **다른 문자열의 중간에서 잘려나왔다** — 그 바이트열(종단 포함)이
                         배열 앞쪽에 존재하되 발견 위치가 **어느 것도 문자열 시작이
                         아니다**. 잔재는 덮어쓰다 남은 꼬리라 원본의 중간부터
                         시작하고, 정당한 항목은 어딘가에 반드시 **문자열 시작으로
                         정식 저장**돼 있다.
  (3) 항목 유일성  — 슬롯 경계 항목끼리 **서로 달라야** 하고 빈 문자열이면 안 된다.
                    선택지 메뉴는 같은 항목을 두 번 싣지 않는다.

(1)만 쓰면 우연한 등간격에 진짜 대사가 걸려 통째로 잘린다. 실제로 `0x13146` 구간
대사가 399→264 로 과절단됐다. (2)만 쓰면 «정당한 중복 저장»과 구별이 안 된다 —
이 게임은 같은 문자열을 여러 번 저장하는 편이라 전체 대사의 63% 가 (2)를 만족한다.

(3)이 필요한 이유: `0x13146` 은 **가변 배치 메뉴**다(「ジューバの店への道」「バエットの
家…」「噂をやめる」…, 항목 간격이 11·11·19·17 로 불규칙). 여기에 step=94 가 우연히
4개 맞았고, 잘려나간 조각들은 **반복 등장하는 정당한 메뉴 항목**이었다.
그때 슬롯 경계로 뽑힌 4개 중 2개가 서로 같은 문자열이었다 — 진짜 메뉴라면 없는 일이다.
`0x49544` 의 빈 문자열 연속(step=16)도 이 판정에서 걸린다.

(2)의 «시작이 아닌 자리» 조건이 결정타다. 처음에는 그냥 «앞쪽에 같은 바이트열이 있으면
잔재»로 봤는데, 이 게임은 같은 문자열을 여러 번 저장하는 편이라 **전체 대사의 63%** 가
거기 걸린다. `0x13146` 에서 잘려나간 「ジューバの店への道」가 바로 그런 경우였다.

★파일명 문자열(`T_JB_040.PCM`)은 **12자+종단 = 13 B 고정**이라 연달아 나오면
  그것만으로 완벽한 등간격이 된다. 반드시 후보에서 빼야 한다 — 안 빼면
  `0x49544` 구간의 대사 127개가 전부 «잔재»로 몰려 사라진다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import strtab

MIN_STEP = 6
MAX_STEP = 96
MIN_ITEMS = 4
BACK = 4096          # 잔재의 원본을 찾아볼 앞쪽 범위
MIN_STALE = 0.8      # 슬롯 내부 조각 중 «앞쪽에 원본이 있는» 것의 최소 비율


def _stale(data, seg, lo, hi, starts, off):
    """seg(종단 포함)가 «다른 문자열의 중간»에서만 발견되는가 = 잔재인가.

    구간 lo..hi 안에서 seg 를 전부 찾아, 발견 위치가 하나라도 문자열 시작이면
    그건 정식으로 저장된 항목이므로 잔재가 아니다.
    ★자기 자신(off)은 당연히 문자열 시작이므로 반드시 빼고 센다.
    """
    found = False
    i = data.find(seg, lo, hi)
    while i >= 0:
        if i != off:
            if i in starts:
                return False
            found = True
        i = data.find(seg, i + 1, hi)
    return found


def find_slot_arrays(data, table, region_start, region_end=None):
    """[(start, step, count, items, junk)] — 검증을 통과한 슬롯 배열만.

    table = strtab.parse_table 결과 [(off, raw, toks)] (구간 하나 분량).
    """
    entries = {o: raw for o, raw, _ in table}
    broken = {o for o, _, t in table if any(k == 'x' for k, _ in t)}
    assets = {o for o, raw, t in table if strtab.is_asset_name(raw)}
    cand = sorted(o for o in entries if o not in assets)
    S = set(cand)
    allo = sorted(entries)
    starts = set(entries)
    if region_end is None:
        region_end = (allo[-1] + len(entries[allo[-1]]) + 1) if allo else region_start

    out = []
    used = set()
    dead = set()
    i = 0
    while i < len(cand):
        o0 = cand[i]
        if o0 in used:
            i += 1
            continue
        best = None
        for step in range(MIN_STEP, MAX_STEP):
            n = 1
            o = o0
            while o + step in S:
                n += 1
                o += step
            if n < MIN_ITEMS:
                continue
            # (3) 슬롯 경계 항목은 서로 달라야 하고, 비어 있으면 안 된다.
            items = [o0 + step * k for k in range(n)]
            vals = [entries[x] for x in items]
            if any(not v for v in vals) or len(set(vals)) != len(vals):
                continue
            # (4) 항목이 슬롯 안에 실제로 들어가야 한다(종단 포함).
            #     안 넣으면 «슬롯 15 B 인데 항목이 40자» 같은 불가능한 결과가 나온다.
            if any(len(v) + 1 > step for v in vals):
                continue
            end = o0 + step * (n - 1)
            junk = [x for x in allo
                    if o0 < x < end and (x - o0) % step != 0 and x not in assets]
            if junk:
                # ★잔재 후보끼리는 서로의 «정식 저장» 근거가 될 수 없다.
                #   같은 꼬리 잔재가 슬롯마다 반복되므로, 빼지 않으면 서로를
                #   가리키며 전부 «정당»으로 판정돼 배열이 하나도 안 잡힌다.
                # ★이미 잔재로 판정된 것들도 «정식 저장»의 근거가 될 수 없다.
                #   빼지 않으면 앞 배열의 잔재가 뒤 배열 판정을 막는다 — 같은 메뉴가
                #   여러 벌 이어지면 첫 벌만 잡히고 나머지가 통째로 남는다.
                eff = starts - set(junk) - dead
                # 원본은 잔재보다 앞에 있다. ★배열 시작까지로 자르면 안 된다 —
                #   잔재의 원본이 **같은 배열의 앞 항목**인 경우가 흔하다
                #   (「『解読の書』の噂」의 꼬리가 다음 슬롯에 「』の噂」로 남는 식).
                #   TWN_SEEK 의 29 B × 15항목 배열이 그래서 통째로 안 잡혔다.
                ok = sum(1 for x in junk
                         if x in broken or
                         _stale(data, entries[x] + b'\x00',
                                region_start, x, eff, x))
                if ok < len(junk) * MIN_STALE:
                    continue
            # 잔재가 아예 없으면 자를 것도 없다 — 슬롯이어도 무해하므로 건너뛴다.
            if not junk:
                continue
            if best is None or n > best[0]:
                best = (n, step, junk)
        if best:
            n, step, junk = best
            items = [o0 + step * k for k in range(n)]
            out.append((o0, step, n, items, junk))
            # ★«배열이 차지한 바이트 범위»를 통째로 소비 대상으로 삼으면 안 된다.
            #   같은 메뉴가 항목을 빼가며 여러 벌 이어 붙는데, 다음 벌의 시작이
            #   앞 배열의 마지막 슬롯 안쪽에 들어와 통째로 건너뛰어진다.
            #   (TWN_SEEK 는 그래서 배열이 1개만 잡히고 미해독 459개가 남았다.)
            #   소비하는 건 «슬롯 경계와 잔재»뿐이다.
            used.update(items)
            used.update(junk)
            dead.update(junk)
        i += 1
    return out


def live_offsets(data, table, region_start, region_end=None):
    """살아 있는 문자열 오프셋 집합 (슬롯 꼬리 잔재를 뺀 것)."""
    live = {o for o, _, _ in table}
    for _, _, _, _, junk in find_slot_arrays(data, table, region_start, region_end):
        live -= set(junk)
    return live


def main():
    import fnt as fntmod
    import regions
    import basemap

    prg, fntpath = sys.argv[1], sys.argv[2]
    verbose = '-v' in sys.argv
    nmax = 0x8000
    if fntpath != '-':
        nmax = 256 + len(fntmod.parse(open(fntpath, 'rb').read()))
    data = open(prg, 'rb').read()

    def render(toks):
        return ''.join(basemap.ch(v) if k in ('g', 'g1')
                       else ('<%02X>' % v if k == 'c' else '<!%02X>' % v)
                       for k, v in toks)

    tot = live_n = tot_ch = live_ch = narr = nitem = 0
    for a, b, _, _, _ in regions.find(data, nmax):
        tab, _ = strtab.parse_table(data, a, nmax, lenient=True)
        tab = [e for e in tab if e[0] < b]
        arrs = find_slot_arrays(data, tab, a, b)
        live = live_offsets(data, tab, a, b)
        narr += len(arrs)
        nitem += sum(x[2] for x in arrs)
        ent = {o: (r, t) for o, r, t in tab}
        if verbose:
            for st, step, n, items, junk in arrs:
                print('배열 0x%06X  슬롯 %d B × %d개  (잔재 %d)' % (st, step, n, len(junk)))
                for o in items:
                    print('   %06X  %s' % (o, render(ent[o][1])))
        for o, raw, t in tab:
            if strtab.is_asset_name(raw):
                continue
            n = sum(1 for k, _ in t if k in ('g', 'g1'))
            tot += 1
            tot_ch += n
            if o in live:
                live_n += 1
                live_ch += n
    print('%s: 슬롯 배열 %d개 / 항목 %d개' % (os.path.basename(prg), narr, nitem))
    print('  대사 %d개 %d자  ->  잔재 제외 %d개 %d자'
          % (tot, tot_ch, live_n, live_ch))


if __name__ == '__main__':
    main()

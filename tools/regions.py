# -*- coding: utf-8 -*-
"""PRG 안의 문자열 테이블 «구간»을 찾는다.

  python tools/regions.py <PRG> <FNT|-> [--us]

세션1의 `textmodel.find_regions` 는 토큰 문법만 봐서 코드까지 긁었다.
여기서는 «널 종단 문자열이 여러 개 연달아 나오는 곳»만 구간으로 인정한다.

★ 이 판정은 «구간을 통째로 점수 매기기»로는 안 된다. lenient 파서가 텍스트를 지나
코드까지 계속 삼켜서, 처음 돌렸을 때 문자열 75,387개(글자는 52,741 — 문자열당 0.7자)
라는 명백한 과다 검출이 나왔다. 그래서 **문자열 단위로 좋고 나쁨을 매기고,
나쁜 문자열이 MAX_GAP 개 연속되면 거기서 자른다**.

  좋은 문자열 = 파일명(asset) 이거나, 글리프 MIN_CH 자 이상이면서 미해독('x') 없음
  구간 채택   = 좋은 문자열 MIN_DIALOG 개 이상 && 문자열당 평균 MIN_AVG 자 이상

★★SH-2 코드 안 ASCII 데이터 배제는 «문자열 단위»로 해야 한다 — 구간 전체의
  1바이트 토큰 비율로 자르면 **진짜 대사 구간이 통째로 탈락한다**. 옛 규칙
  `MAX_1BYTE = 0.30` 이 실제로 그랬다:

      TWN_CARA 0x00ECEC  1바이트 비율 0.31 → 대사 241개 탈락
      TWN_SEEK 0x0061C2               0.33 → 160개 탈락
      MENUEN   0x0029A8               0.22 → 몬스터 도감 218개 탈락(구간 자체를 못 찾음)
      TWN_ZOAH 0x01C9C3               0.53 → 구간 조기 절단

  1바이트 토큰은 글리프 index 0x20~0x7F = 「な~ン」이다. な·に·の·は·ま·ん과
  가타카나는 일본어에서 아주 흔하므로, **구간에 따라 1바이트가 절반을 넘는 게
  정상**이다. 「드물다」던 관찰은 첫 구간 하나만 보고 일반화한 것이었다.
  → [[feedback_kr_patch_verification]] 「한 화면 보고 일반화 금지」의 재판.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import fnt as fntmod
import strtab

MIN_CH = 2
MIN_DIALOG = 5
MIN_AVG = 4.0
MAX_GAP = 5

PRINTABLE = re.compile(rb'^[\x20-\x7e]+$')
FMT = re.compile(rb'%[0-9]*[dsxu]')
WORD = re.compile(rb'[A-Za-z]{3}')


def is_ascii_data(raw, toks):
    """SH-2 코드 안의 디버그·서식 문자열인가 — `phase %1d`, `NO ENCOUNT AREA`.

    1바이트 토큰이 글리프 index 0x20~0x7F 를 가리키므로 이런 ASCII 데이터가
    그대로 «일본어 대사»로 렌더돼 눈으로도 안 걸러진다(「ホニソムテなはよツ」).

    판정 = **2바이트 글리프가 하나도 없고** + 전부 인쇄 가능 ASCII +
           서식(`%2d`) 이나 영단어꼴(영문자 3연속). 실측 검증:
      · 알려진 디버그 문자열 8종 전부 True
      · 진짜 대사 4구간(1바이트 비율 0.22~0.53) 오검출 0
        — 걸린 건 `T_FE_002.PCM` 같은 **파일명뿐**이라 먼저 뺀다.
    """
    if strtab.is_asset_name(raw):
        return False
    if any(k == 'g' for k, _ in toks):
        return False
    if not PRINTABLE.match(raw):
        return False
    return bool(FMT.search(raw) or WORD.search(raw))


def is_good(raw, toks, ascii_data=False):
    if any(k == 'x' for k, _ in toks):
        return False
    k = strtab.kind(raw, toks)
    if k == 'asset':
        return True
    if not ascii_data and is_ascii_data(raw, toks):
        return False
    return k == 'glyph' and sum(1 for a, _ in toks if a in ('g', 'g1')) >= MIN_CH


def split_runs(tab, ascii_data=False):
    """좋은 문자열이 밀집한 조각들로 나눈다."""
    runs = []
    cur = []
    gap = 0
    for ent in tab:
        if is_good(ent[1], ent[2], ascii_data):
            cur.append(ent)
            gap = 0
        else:
            gap += 1
            if gap > MAX_GAP:
                if cur:
                    runs.append(cur)
                cur = []
            elif cur:
                cur.append(ent)
    if cur:
        runs.append(cur)
    # 꼬리에 붙은 나쁜 문자열 제거
    out = []
    for r in runs:
        while r and not is_good(r[-1][1], r[-1][2], ascii_data):
            r.pop()
        if r:
            out.append(r)
    return out


def accept(run, ascii_data=False):
    """구간으로 인정할까.

    ★세 갈래다 — 하나(①)만 쓰면 «짧은 이름표»와 «긴 지문 두어 개»를 놓친다.
      ② 없이 돌리면 `BTL_A3` 0x531B0 의 적 이름·기술명 표(「シャプリ」「大アゴ」
        「串刺し」 13개, 평균 3.8자)가 MIN_AVG 4.0 에 걸려 통째로 탈락한다.
      ③ 없이 돌리면 `MENUEN` 몬스터 도감이 탈락한다 — 「이름 + 해설」 2개씩
        끊겨 있어 MIN_DIALOG 5 를 못 채운다(해설 하나가 70자인데도).
    """
    ok = [e for e in run if is_good(e[1], e[2], ascii_data)]
    good = len(ok)
    nch = sum(1 for _, _, t in run for k, _ in t if k in ('g', 'g1'))
    # ★글자 수는 «좋은 문자열만» 센다. 전체로 세면 사이에 낀 바이너리 쓰레기가
    #   글자 수를 채워줘서, 진짜 대사 2개 + 쓰레기 5개짜리 런이 통과한다
    #   (1ST_READ·BTL_A3 에서 실제로 그렇게 수백 건이 새어 들어왔다).
    gch = sum(1 for _, _, t in ok for k, _ in t if k in ('g', 'g1'))
    if good < 2:
        return False
    # ① 기본 — 보통 길이의 대사가 여럿
    if good >= MIN_DIALOG and nch >= len(run) * MIN_AVG:
        return True
    # ② 이름표·기술명 표 — 짧지만 나쁜 문자열 하나 없이 빈틈없이 이어진다.
    #    density 1.0 을 요구해 «우연히 토큰화된 바이너리»를 막는다.
    if good >= MIN_DIALOG and good == len(run) and gch >= len(run) * 2.0:
        return True
    # ③ 긴 지문이 두어 개 — 도감 해설. 문자열당 8자 이상 && 합계 24자 이상.
    if gch >= 24 and gch >= good * 8:
        return True
    return False


def find(data, nmax, ascii_data=False):
    """[(start, end, nstr, nchar, nasset)] — 겹치지 않는 구간 목록."""
    out = []
    i = 0
    n = len(data)
    while i < n - 4:
        b = data[i]
        # 시작 후보 = 글리프 토큰. JP 본문은 2바이트가 주력이지만 US 본문은
        # 1바이트(ASCII)가 주력이라, 2바이트로 시작하는 곳만 보면 구간을 크게 놓친다.
        if b >= 0x80:
            ok = (((b & 0x7F) << 8) | data[i + 1]) < nmax
        else:
            ok = ascii_data and b >= 0x20
        if not ok:
            i += 1
            continue
        tab, end = strtab.parse_table(data, i, nmax, lenient=True)
        runs = [r for r in split_runs(tab, ascii_data) if accept(r, ascii_data)]
        if not runs:
            i += 1
            continue
        for r in runs:
            e = r[-1][0] + len(r[-1][1]) + 1
            nch = sum(1 for _, _, t in r for k, _ in t if k in ('g', 'g1'))
            na = sum(1 for _, raw, t in r if strtab.kind(raw, t) == 'asset')
            out.append((r[0][0], e, len(r), nch, na))
        i = max(out[-1][1], i + 1)
    return out


def main():
    prg, fntpath = sys.argv[1], sys.argv[2]
    nmax = 0x8000
    if fntpath != '-':
        nmax = 256 + len(fntmod.parse(open(fntpath, 'rb').read()))
    data = open(prg, 'rb').read()
    regs = find(data, nmax)
    print('# %s  (%d B, nmax=%d)' % (os.path.basename(prg), len(data), nmax))
    print('%-21s %7s %8s %7s' % ('구간', '문자열', '글자', '파일명'))
    for a, b, ns, nc, na in regs:
        print('0x%06X..0x%06X %7d %8d %7d' % (a, b, ns, nc, na))
    print('---- 구간 %d개, 문자열 %d, 글자 %d, 파일명 %d'
          % (len(regs), sum(r[2] for r in regs), sum(r[3] for r in regs),
             sum(r[4] for r in regs)))


if __name__ == '__main__':
    main()

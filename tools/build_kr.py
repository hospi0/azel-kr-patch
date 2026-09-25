# -*- coding: utf-8 -*-
"""한글 패치 빌드 — 폰트 굽기 + 텍스트 교체 + 디스크 쓰기.

  python tools/build_kr.py <원본 Track1.bin> <출력 Track1.bin> [--dry]

입력
  work/trans/test_ko.tsv   번역표 (id, ko)
  work/trans/t2.tsv        대상 단위 (id, mod, budget, jp)
  work/trans/places.tsv    각 단위의 모든 출현 위치

하는 일
  1. 번역문에 쓰인 글자를 기본 폰트 슬롯에 배정한다(§alloc).
     **1바이트 구간(0x20~0x7F)에 최빈 글자**를 두는 게 예산의 핵심이다.
  2. `COMMON.DAT` 의 기본 폰트 자리에 갈무리11 한글 글리프를 굽는다(§7.26).
  3. 각 PRG / MOVIE.DAT 의 원문 자리를 **같은 길이로** 덮어쓴다(§7.25).
     짧으면 공백 글리프로 채운다 — 길이가 바뀌면 순차 소비가 어긋난다.
  4. MODE1/2352 섹터에 쓰면서 **EDC/ECC 를 재계산**한다.
     안 하면 내용과 무관하게 크래시한다.
"""
import os
import re
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import alloc
import basemap
import cdrom_ecc
import encode as enc
import krglyph
from iso9660 import Iso, SECTOR, DATA_OFF, DATA_LEN

BASE_OFF = 0x1068A          # COMMON.DAT 안 기본 폰트
ITEMS_TSV = 'work/trans/items.tsv'
# 원본 이름표에 «실제로 쓰인» 문자만 허용한다 — 나머지는 렌더 결과가 미검증이다.
# ⛔소문자는 기본 폰트에 **없다** — `a` 는 `究`, `z` 는 `表` 로 나온다.
ITEM_OK = set('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-?')
# 이름칸 화면 폭. 원본이 «그려지는 글자» 기준 최대 8이고, 9자는 수량 `x` 에
# 딱 붙으며 10자는 잘린다(실기 실측).
ITEM_WIDTH = 8
# 글자당 2바이트를 무조건 읽는 렌더러를 쓰는 모듈(실기 실측으로만 늘린다).
NO_1BYTE_MODULES = {'BTL_T0'}

# ★★2026-08-15 실기로 확정된 «문자열이 아닌 자리». 여기에 번역을 쓰면 안 된다.
#   (module, 파일오프셋)
#   BTL_A5 0x4F91F : 추출기가 `81 29 00` 을 「鈴」+종단으로 읽었지만, 실제로는
#     **SH-2 코드 한가운데의 홀수 오프셋**이다. 앞뒤 워드가 `8481 | 2900 | E052`
#     인데 번역을 넣으면 `2900`(mov.b R0,@R9)이 `1C00`(mov.l R0,@(0,R12))로
#     바뀐다. 바로 위에서 `R9 = R2+96` 을 만든다 — 적 구조체에 «약점 표시»
#     플래그를 세우는 명령이었고, 이게 깨져서 전투 중 약점 마커가 통째로
#     안 나왔다(원본 12개 → 패치 0개, 실기 이분법으로 이 한 곳까지 좁힘).
#   지문 = 「글자 하나짜리 + 앞뒤로 수만 바이트 떨어진 외딴 자리 + 홀수 오프셋」.
# ★★여기 적힌 자리는 «텍스트가 아니다» — 원본 바이트를 그대로 둔다.
#   ▸ BTL_A5 0x4F91F : SH-2 «실행 코드». 덮었더니 `mov.b R0,@R9` 가 다른
#     명령으로 바뀌어 적 약점(WEAK) 표시가 사라졌다(2026-08-15 실기 확인).
#   ▸ 아래 3곳 : 원본이 **순수 ASCII 문자열**이다. 글리프 토큰으로 오독해
#     번역 단위가 됐지만, 이 자리를 읽는 쪽은 printf 계열 ASCII 경로다.
#     MENUEN 0x28A8 은 원본 `"     "`(ASCII 공백 5칸)인데 우리가 1바이트
#     공백 글리프(index 0x29)로 채워 화면에 `)))))` 가 4줄 떴다(실기 확인).
#     주변이 `"R" "G" "B" "L" ":%3d"` 인 것으로 ASCII 표임이 확정된다.
#     ⚠판정법 = «원본 슬롯 바이트가 전부 0x20~0x7E». verify_ascii.py 가 검사한다.
BLOCKED_PLACES = {
    ('BTL_A5', 0x4F91F),
    ('MENUEN', 0x28A8),     # "     "  → `)))))`
    ('FLD_D2', 0x7F95),     # "6@"     (→ 'ろ？' 로 오독)
    ('FLD_A3', 0x8E55),     # "@ "     (→ '？な' 로 오독)
    # 2026-08-15 `verify_term.py` 가 잡음: 문자열 «중간»에서 시작한 거짓 검출
    # (`<!BD>た` 1글자, bud=4)인데, 그 자리를 쓰면 원본 제어코드 `1B` 가
    # 글리프 `F7` 로 바뀌어 토큰 폭이 어긋난다 — 뒤의 `T_PT_309.PCM` 까지 밀린다.
    ('TWN_CAMP', 0xE56E),
}
# ★★2026-08-15: «토큰 폭»이 원본과 어긋나 제어코드·종단자 구조가 깨진 자리.
#   원본이 1바이트 글리프 토큰을 안 쓰던 자리에 우리가 섞으면 뒤가 밀린다.
#   ⛔전면 적용은 못 한다 — 1바이트가 예산을 벌어주고 있어 2,659곳이 초과한다.
#     `verify_ctrl.py` 가 구조 파손으로 잡아낸 자리만 지정해 되돌린다.
FORCE_2BYTE_PLACES = {
    ('TWN_EXCA', 0x0018B7),   # )<1D><1A><01>(…안 돼,벌써 차갑게 식었어)
    ('TWN_CARA', 0x00B007),   # )<1D><1A><01>(먹이라도 줘볼까…)
    ('TWN_CARA', 0x017C5D),   # 와줬으면 한다는군
}
# ★원본이 **KEEP 글자를 2바이트로** 쓴 자리(전체 6,797곳 중 구조가 깨진 것만).
#   TWN_ZOAH 0x2F534 원본 `36 80 40 00` = 「ろ」1바이트 + 「？」**2바이트**.
KEEP_2BYTE_PLACES = {
    ('TWN_ZOAH', 0x02F534),   # 지？
    ('TWN_EXCA', 0x0018B7),   # 원본은 `(` `…` `)` 를 2바이트로 쓴다
    ('TWN_CARA', 0x00B007),
}
TOK = re.compile(r'<!([0-9A-F]{2})>|<([0-9A-F]{2})>|\\n|(.)', re.S)


def load_tsv(path, keycol=0):
    rows = []
    with open(path, encoding='utf-8') as f:
        head = f.readline().rstrip('\n').split('\t')
        for line in f:
            line = line.rstrip('\n')
            if line:
                rows.append(line.split('\t'))
    return head, rows


def chars_of(ko):
    return [m.group(3) for m in TOK.finditer(ko)
            if m.group(3) and m.group(3) not in basemap.REVERSE_KEEP]


PURE = 'work/purebase.pkl'
ONEB = 'work/allow1b.pkl'


def allow_1byte_texts():
    """원본이 «1바이트 글리프 토큰»을 실제로 쓴 문자열의 집합.

    ★그 밖의 문자열에는 1바이트를 쓰면 안 된다 — 그런 자리를 그리는 렌더러는
      글자당 2바이트를 무조건 읽어서, 1바이트가 섞이면 뒤가 통째로 어긋난다.
      실기에서 「호밍 레이저」 뒤에 `이이이…스공줌` 이 붙었고, 번역이 짧을수록
      쓰레기가 길어졌다(= 어긋난 뒤 계속 읽는다는 지문).
    """
    import pickle
    if os.path.exists(ONEB):
        return pickle.load(open(ONEB, 'rb'))
    import textmodel2
    s = set()
    for it in textmodel2.collect('work/uniq'):
        if any(k == 'g1' for k, _ in it['toks']):
            s.add(it['text'])
    pickle.dump(s, open(ONEB, 'wb'))
    return s


def pure_base_texts():
    """원본이 **기본 폰트 글자로만** 돼 있는 문자열의 집합.

    ★`COMMON.DAT` 은 상주 데이터라 어느 장면 폰트가 물릴지 정해져 있지 않다 —
      그래서 한때 「COMMON.DAT 텍스트는 전부 기본 폰트로」라고 못박았는데,
      그러면 350글자가 필요해 197칸에 안 들어간다.

    정밀하게 보면 제약을 받는 건 그중 일부뿐이다. **원본이 이미 index>=256
    (장면 FNT) 을 쓰고 있는 문자열**은 그 자리에서 그 폰트가 확실히 물린다는
    뜻이므로 우리도 같은 FNT 를 써도 된다(실측: 192개가 `ITEM`/`MENU`).
    진짜 위험한 건 **원본이 기본 폰트 글자만 쓴** 문자열이다 — 원작자가
    일부러 그렇게 짠 자리다. 그건 40개·70글자뿐이라 넉넉히 들어간다.
    """
    import pickle
    if os.path.exists(PURE):
        return pickle.load(open(PURE, 'rb'))
    import textmodel2
    s = set()
    for it in textmodel2.collect('work/uniq'):
        if not any(k in ('g', 'g1') and v >= 256 for k, v in it['toks']):
            s.add(it['text'])
    pickle.dump(s, open(PURE, 'wb'))
    return s


RESIDENT_MODULES = ('1ST_READ',)     # 어느 장면 폰트가 물릴지 정해지지 않은 상주 모듈


def resident_pure_ids(places_by_id):
    """상주 모듈 자리인데 **원본이 기본 폰트 글자만** 쓰던 단위의 id 집합.

    원작자가 그런 자리를 기본 폰트만으로 짠 것은 «어느 화면에서 그려져도 안전하게»
    라는 뜻이다. 우리가 장면 FNT 칸에 넣으면 다른 폰트가 물린 화면에서 깨진다
    ([[feedback_shared_text_needs_shared_font]]).
    """
    ids = set()
    for mod in RESIDENT_MODULES:
        src = os.path.join('work', 'uniq', mod + '.PRG')
        if not os.path.exists(src):
            continue
        d = open(src, 'rb').read()

        def pure_here(off, bud):
            i, e = off, min(off + bud, len(d) - 1)
            while i < e:
                b = d[i]
                if b == 0:
                    return True
                if b >= 0x80:
                    if (((b & 0x7F) << 8) | d[i + 1]) >= 256:
                        return False
                    i += 2
                else:
                    i += 1
            return True

        for uid, pls in places_by_id.items():
            here = [p for p in pls if p[2] == mod]
            if here and all(pure_here(int(p[4], 16), int(p[5])) for p in here):
                ids.add(uid)
    return ids


def cost_parts(ko, base_set):
    """(고정 바이트, 기본폰트 글자별 개수) — 1바이트 칸 배정의 입력.

    고정분 = 제어코드 1B + 유지글자(원래 index 로 1 또는 2B) + 장면FNT 글자 2B
             + 종단 1B. 기본폰트 글자는 1바이트 칸을 받으면 2→1 로 줄어든다.
    """
    fixed = 1
    cnt = Counter()
    for m in TOK.finditer(ko):
        ctrl, ch = m.group(1) or m.group(2), m.group(3)
        if ctrl is not None or ch is None:
            fixed += 1
            continue
        idx = basemap.REVERSE_KEEP.get(ch)
        if idx is not None:
            fixed += 1 if 0x20 <= idx < 0x80 else 2
        elif base_set is None or ch in base_set:
            fixed += 2
            cnt[ch] += 1
        else:
            fixed += 2
    return fixed, cnt


def pick_one_byte(ko_by_id, places_by_id, budget_of, base_set, nslots):
    """1바이트 칸을 받을 글자 고르기 — «안 들어가는 문자열 수»를 최소화한다.

    탐욕법: 매번 «넘치는 문자열을 가장 많이 구제하는 글자»를 뽑는다.
    동점이면 총 초과 바이트를 가장 많이 줄이는 쪽.
    """
    items = []
    for uid, ko in ko_by_id.items():
        b = budget_of.get(uid)
        if b is None:
            continue
        fixed, cnt = cost_parts(ko, base_set)
        if cnt:
            items.append([fixed - b, cnt])      # 여유가 음수면 이미 들어감

    chosen = []
    for _ in range(nslots):
        fix = Counter()
        cut = Counter()
        for over, cnt in items:
            if over <= 0:
                continue
            for c, k in cnt.items():
                cut[c] += min(k, over)
                if k >= over:
                    fix[c] += 1
        if not cut:
            break
        c = max(cut, key=lambda k: (fix[k], cut[k]))
        chosen.append(c)
        for it in items:
            it[0] -= it[1].pop(c, 0)
    return chosen


def load_fnt_reserved():
    """{fnt: {index,…}} — «번역하지 않는 문자열이 아직 가리키는» 장면 FNT 칸.

    ★★이 칸을 재활용하면 **원문 그대로 둔 문자열이 화면에서 깨진다.**
      실기(2026-08-15): 도감 DATA 화면의 단위 표기 `m`/`cm`/`kg` 가
      `괴`/`관`/`감` 으로 나왔다 — `MENUEN.FNT` 274~277 을 한글로 덮었기 때문.
      그 자리(`MENUEN.PRG 0x1E55` 의 `81 12`)는 우리가 손대지 않으므로
      되읽기 검증으로는 **원리상 안 잡힌다**.
    표는 `tools/fnt_reserved.py` 가 무수정 원본에서 만든다.
    """
    p = 'work/fnt_reserved.tsv'
    out = {}
    if not os.path.exists(p):
        print('⚠work/fnt_reserved.tsv 가 없다 — fnt_reserved.py 를 먼저 돌릴 것')
        return out
    with open(p, encoding='utf-8') as f:
        f.readline()
        for line in f:
            c = line.rstrip('\n').split('\t')
            if len(c) == 2:
                out.setdefault(c[0], set()).add(int(c[1]))
    return out


def build_charmap(ko_by_id, places_by_id, fnt_sizes, jp_of, budget_of):
    """글자 → index 배정.

    반환 (base_used, scene_used, pad1)
      base_used   {글자: index}          기본 폰트 (전 모듈 공유)
      scene_used  {fnt: {글자: index}}   장면 폰트 (index 는 256~)

    기본 폰트가 좁으므로(197칸) **최빈 글자를 여기에**, 나머지는 그 글자가
    쓰이는 모듈의 `.FNT` 에 넣는다. FNT 는 원래 글리프 수를 넘기지 않는다
    (크기가 바뀌면 ISO 를 다시 짜야 한다).
    """
    pure = pure_base_texts()
    reserved = load_fnt_reserved()
    resident_pure = resident_pure_ids(places_by_id)

    def cap_of(fn):
        """그 FNT 에서 **우리가 실제로 쓸 수 있는** 칸 수(예약 칸 제외)."""
        return fnt_sizes.get(fn, 0) - len(reserved.get(fn, ()))

    def free_slots(fn):
        return [256 + i for i in range(fnt_sizes.get(fn, 0))
                if 256 + i not in reserved.get(fn, ())]

    freq = Counter()
    per_fnt = {}
    must_base = set()
    for uid, ko in ko_by_id.items():
        pls = places_by_id.get(uid, ())
        cs = chars_of(ko)
        for c in cs:
            freq[c] += max(1, len(pls))
        # ★`COMMON.DAT` 이면서 **원본이 기본 폰트만 쓰던** 자리만 기본 폰트로
        #   묶는다. 상주 데이터라 장면 폰트가 어느 게 물릴지 모르는 자리이기
        #   때문이다(「판매」를 MENU.FNT 에 넣었더니 다른 화면에서 「판승」).
        #   ⛔`COMMON.DAT` 전체를 묶으면 350글자가 필요해 197칸을 못 맞춘다.
        is_pure = jp_of.get(uid) in pure
        if any(p[1] == 'COMMON' for p in pls) and is_pure:
            must_base.update(cs)
        # ★★2026-08-15 실기: 세이브 확인창의 「예 아니오」가 **「결 아니오」**로 나왔다.
        #   자리는 `1ST_READ.PRG 0x03D68F`(짝 폰트 SAVE.FNT)인데, 1ST_READ 는
        #   **상주 모듈**이라 그 창이 뜰 때 물려 있는 건 그 «장면»의 FNT 다.
        #   「예」만 SAVE.FNT index 16 에 배정돼(「아니오」는 기본폰트) 다른 폰트의
        #   16번 글자가 나온 것 — 「판매」→「판승」과 같은 유형
        #   ([[feedback_shared_text_needs_shared_font]]).
        #   ⚠`pure_base_texts()` 는 이 문자열을 못 잡았다(collect 의 텍스트 표현이
        #     units 의 jp 와 달라 집합 대조가 빗나간다). 그래서 판정을 문자열이 아니라
        #     **자리의 원본 바이트**로 한다 — 그쪽이 진실 원천이다.
        if uid in resident_pure:
            must_base.update(cs)
        # ★★2026-08-15 실기: 지명 상자의 「캐러밴」이 **「가?러밴」**으로 나왔다.
        #   이 이름들은 `1ST_READ`(SAVE.FNT)와 `WORLD`(WORLDMAP.FNT) 양쪽에 있는데,
        #   **원본은 가나뿐이라 전부 기본폰트**였다 — 즉 어느 화면에서 그려져도
        #   안전하도록 원작자가 그렇게 짠 자리다. 우리가 장면 FNT 칸에 넣으면
        #   그 상자가 뜨는 화면에 다른 폰트가 물려 엉뚱한 글자가 나온다
        #   ([[feedback_shared_text_needs_shared_font]] 「판매」→「판승」과 같은 유형).
        #   ⛔「원본이 기본폰트만 쓰는 단위 전부」로 넓히면 491자라 197칸에 안 들어간다.
        #     실기로 깨진 이 갈래(지명 3개·한글 7자)만 묶는다.
        #   ★★그리고 기본폰트에 넣는 것만으로는 부족했다 — **index 가 낮아야 한다.**
        #     실기 실측(2026-08-15): 라 0x2F·반 0x8E·러 0x31·밴 0x97 은 제대로 나오는데
        #     카 0xBA·캐 0xBC·캠 0xEB·프 0xA4 는 엉뚱한 글자로 나왔다.
        #     ⇒ 이 상자는 **기본폰트 앞쪽 일부만** VRAM 에 올린다. 경계는
        #       «0x97 정상 / 0xA4 깨짐» 사이이므로 안전하게 **0x98 미만**을 쓴다.
        # (2026-08-15: 지명 기본폰트 강제는 실기로 효과가 확인되지 않아 되돌림.
        #  상자 렌더러의 토큰 해석을 코드로 확인한 뒤 다시 판단한다.)
        for p in pls:
            # ★`COMMON.DAT` 자리도 «원본이 장면 FNT 를 쓰던» 것이면 그 FNT 에
            #   글자를 실어야 한다. 예전엔 COMMON 을 통째로 기본폰트로 몰았기
            #   때문에 여기서 빼도 됐지만, 이제는 빼면 슬롯이 아예 안 생긴다.
            if p[3] and (p[1] != 'COMMON' or not is_pure):
                per_fnt.setdefault(p[3], set()).update(cs)

    # ★2026-08-15 실험: 특정 글자를 **기본 폰트(전 모듈 공유)** 로 강제한다.
    #   여러 모듈에 같이 실리는 문자열(적 이름 등)은 장면 FNT 칸에 배정되면
    #   **모듈마다 index 가 달라 바이트가 갈라진다** — 원문은 가나라 전부
    #   기본 폰트였으므로 어느 모듈에서도 같은 바이트였다.
    #   환경변수 `AZEL_BASE_CHARS` 에 글자를 이어 쓰면 그 글자들이 기본 폰트로 간다.
    forced = os.environ.get('AZEL_BASE_CHARS', '')
    if forced:
        must_base.update(forced)
        print('기본 폰트 강제 배정: %s' % ' '.join(forced))

    one = list(alloc.ONE_BYTE)
    two = list(alloc.TWO_BYTE)
    enc.PAD_1B = one.pop()
    cap_total = len(one) + len(two)

    # ⛔«1바이트가 꼭 필요한 글자를 기본 폰트에 넣는다» 를 해봤는데 역효과였다
    #   (넘침 39→133). 그런 글자는 대개 드물어서, 기본 폰트 자리를 그쪽에 쓰면
    #   여러 문자열을 한꺼번에 살리는 흔한 글자가 장면 FNT 로 밀려난다.
    #   1바이트가 아니면 도저히 안 되는 자리는 «번역을 줄이는» 게 맞다.

    # --- 어떤 글자를 기본 폰트에 둘지 «고른다» -------------------------------
    # ★빈도만 보고 고르면 안 된다. 기본 폰트는 전 모듈이 공유하므로, 칸이
    #   모자란 장면 FNT 가 있으면 **그 FNT 가 쓰는 글자**를 기본으로 올려야
    #   숨통이 트인다. 빈도순으로만 채웠더니 `FLD_T0` 가 11칸 모자랐다.
    chosen = set(must_base)
    if len(chosen) > cap_total:
        raise SystemExit('기본 폰트에 반드시 들어가야 할 글자가 넘침: %d > %d'
                         % (len(chosen), cap_total))

    def overflow():
        out = {}
        for fn, cs in per_fnt.items():
            n = len(cs - chosen) - cap_of(fn)
            if n > 0:
                out[fn] = n
        return out

    while len(chosen) < cap_total:
        over = overflow()
        if not over:
            break
        # 넘치는 FNT 를 가장 많이 구제하는 글자부터 (동점이면 빈도순)
        score = Counter()
        for fn in over:
            for c in per_fnt[fn] - chosen:
                score[c] += 1
        c = max(score, key=lambda k: (score[k], freq[k]))
        chosen.add(c)
    over = overflow()
    if over:
        # ★실험용: 넘치면 멈추지 말고 «못 들어간 글자»를 버리고 강행한다.
        #   빌드가 되는지/화면이 어떻게 되는지 보려면 완결성보다 결과가 먼저다.
        if os.environ.get('AZEL_FORCE'):
            print('⚠FNT 칸 부족 %d개 폰트 — 강행(못 들어간 글자는 버린다)'
                  % len(over))
        else:
            raise SystemExit('FNT 칸 부족(기본 폰트를 다 써도 모자람): %s'
                             % ', '.join('%s %d개' % (k, v)
                                         for k, v in over.items()))

    # 남는 기본 폰트 칸은 빈도 높은 글자로 채운다(2바이트→1바이트 절약).
    for c, _ in freq.most_common():
        if len(chosen) >= cap_total:
            break
        chosen.add(c)

    # --- 1바이트 칸을 «예산이 빠듯한 문자열»에 쓴다 -------------------------
    # ★최빈 글자에 주는 게 당연해 보이지만 틀렸다. 번역문은 예산에 맞춰
    #   **공백으로 패딩**되므로 여유 있는 문자열이 짧아져도 아무 이득이 없다.
    #   1바이트 칸의 유일한 값어치는 «안 들어가는 문자열을 들어가게» 하는 것뿐.
    #   빈도순으로 줬을 때 743건이 넘쳤다.
    onebyte = pick_one_byte(ko_by_id, places_by_id, budget_of, chosen,
                            len(one))

    base_used = {}
    for c in onebyte:
        base_used[c] = one.pop(0)
    for c, _ in freq.most_common():
        if c in chosen and c not in base_used:
            base_used[c] = one.pop(0) if one else two.pop(0)
    for c in sorted(chosen):
        if c not in base_used:
            base_used[c] = one.pop(0) if one else two.pop(0)

    scene_used = {}
    for fn, cs in per_fnt.items():
        rest = sorted(c for c in cs if c not in base_used)
        slots = free_slots(fn)
        if len(rest) > len(slots):
            if os.environ.get('AZEL_FORCE'):
                rest = rest[:len(slots)]
            else:
                raise SystemExit('FNT %s 칸 부족: %d글자 필요, %d칸(예약 %d칸 제외)'
                                 % (fn, len(rest), len(slots),
                                    len(reserved.get(fn, ()))))
        scene_used[fn] = {c: slots[i] for i, c in enumerate(rest)}
    base_used = reorder_for_name_entry(base_used)
    # ★배정표를 남긴다. 번역문이 조금만 바뀌어도 «글자→index» 가 통째로 달라진다.
    #   실기 스샷의 깨진 글자를 역추적할 때 **그 빌드의 배정**이 없으면 아무것도
    #   못 맞춘다(실제로 바뀐 배정으로 역추적하다 하루를 날렸다).
    with open('work/charmap.tsv', 'w', encoding='utf-8', newline='') as f:
        f.write('scope\tchar\tindex\n')
        for c, i in sorted(base_used.items(), key=lambda kv: kv[1]):
            f.write('base\t%s\t%d\n' % (c, i))
        for fn, m in sorted(scene_used.items()):
            for c, i in sorted(m.items(), key=lambda kv: kv[1]):
                f.write('%s\t%s\t%d\n' % (fn, c, i))

    left = [c for c in freq if c not in base_used]
    print('배정: 기본폰트 %d글자, 장면FNT %d개(최대 %d글자), 기본밖 %d글자'
          % (len(base_used), len(scene_used),
             max((len(v) for v in scene_used.values()), default=0), len(left)))
    return base_used, scene_used, enc.PAD_1B


def build_patch():
    """{파일명: {오프셋: 바이트열}} — 디스크에 써야 할 것 전부.

    빌더와 검증기가 **같은 코드**로 기대값을 만들게 하려고 떼어냈다.
    따로 계산하면 「내 데이터엔 이상 없음」류 헛검증이 된다.
    """

    # ★번역표의 키는 «원문 텍스트»다. units.tsv 를 다시 만들면 id 가 바뀌므로
    #   id 를 키로 쓰면 번역이 통째로 엉뚱한 자리에 붙는다.
    _, units = load_tsv('work/trans/units.tsv')
    id_of = {u[5]: u[0] for u in units}
    budget = {u[0]: int(u[3]) for u in units}
    _, korows = load_tsv('work/trans/ko.tsv')
    ko_by_id = {}
    miss = []
    same = 0
    for r in korows:
        if len(r) < 2 or not r[1]:
            continue
        # ★번역이 원문과 같으면 아예 건드리지 않는다. 같은 바이트를 되쓰는 건
        #   의미가 없는데, 그 글자들이 글리프 슬롯을 잡아먹어 정작 번역이 필요한
        #   글자가 밀려난다. 장식 문자열(♪★■)·서식 문자열(` %4d `)이 여기 든다.
        if r[1] == r[0]:
            same += 1
            continue
        uid = id_of.get(r[0])
        if uid is None:
            miss.append(r[0])
        else:
            ko_by_id[uid] = r[1]
    if same:
        print('원문 그대로인 %d단위는 건드리지 않는다' % same)
    if miss:
        print('★원문을 못 찾은 번역 %d개: %s' % (len(miss), miss[:3]))
    _, places = load_tsv('work/trans/places.tsv')
    places_by_id = {}
    for p in places:
        places_by_id.setdefault(p[0], []).append(p)

    import fnt as fntmod
    srcdir = 'work/uniq'
    fnt_sizes = {f[:-4]: len(fntmod.parse(open(os.path.join(srcdir, f), 'rb').read()))
                 for f in os.listdir(srcdir) if f.endswith('.FNT')}
    jp_of = {u[0]: u[5] for u in units}
    # ★1바이트 토큰을 받아들이지 않는 «렌더러»가 있다 — 그 모듈의 문자열은
    #   전부 2바이트로 써야 한다. 실기에서 `BTL_T0`(전투 튜토리얼)이 깨졌다.
    #   ⛔전 문자열에 적용하면 안 된다 — 원본이 1바이트를 쓴 건 2.9%뿐인데
    #     나머지 6,760개는 1바이트로도 멀쩡히 나온다(예산 초과만 3,452건 늘어난다).
    # ★지명 상자는 가운데 정렬이라 패딩을 앞뒤로 나눠야 글자가 가운데 온다.
    #   지명 상자가 읽는 건 **필드 모듈(TWN_*)의 `)`+제어코드로 시작하는 자리**다
    #   (탐침으로 확정: `1ST_READ`/`WORLD` 사본을 바꿔도 화면이 안 변했다).
    center_pad = set()
    for uid, pls in places_by_id.items():
        jp = jp_of.get(uid, '')
        if jp.startswith(')') and any(p[2].startswith('TWN_') for p in pls):
            center_pad.add(uid)
    one_ok = allow_1byte_texts()
    pure_txt = pure_base_texts()
    no1b = set()
    for uid, pls in places_by_id.items():
        mods = {p[2] for p in pls}
        hit = bool(mods & NO_1BYTE_MODULES)
        # ★★2026-08-15 실기: 지명 상자도 «글자당 2바이트를 무조건 읽는» 렌더러다.
        #   `TWN_CARA.PRG 0x38AF` 의 「キャラバン」 자리는 원본이 2바이트 토큰만
        #   쓰는데(`80 59 80 4e 80 79 80 97 80 7f 00`), 우리가 예산을 맞추려고
        #   1바이트 토큰(`7f`)을 섞었더니 그 뒤가 통째로 어긋나 상자에
        #   「가·깨짐·라·반」 이 나왔다. 지명 갈래(원본이 기본폰트만 쓰고
        #   `1ST_READ`+`WORLD` 양쪽에 있는 단위)도 1바이트를 금지한다.
        if not hit and jp_of.get(uid) in pure_txt                 and '1ST_READ' in mods and 'WORLD' in mods:
            hit = True
        if hit and jp_of.get(uid) not in one_ok:
            no1b.add(uid)
    print('1바이트 금지 단위 %d개 (%s)'
          % (len(no1b), ','.join(sorted(NO_1BYTE_MODULES))))
    base_used, scene_used, pad1 = build_charmap(ko_by_id, places_by_id,
                                                fnt_sizes, jp_of, budget)
    base_map = dict(basemap.REVERSE_KEEP)
    base_map.update(base_used)

    # --- 1) 인코딩 + 예산 검사 (자리마다 그 모듈의 FNT 배정을 쓴다) -------
    _of = os.environ.get('AZEL_TEXT_OFF')
    if _of:
        _lo, _hi = [int(x, 16) for x in _of.split('-')]
        print('⚠AZEL_TEXT_OFF — 오프셋 0x%X~0x%X 만 번역' % (_lo, _hi))
    else:
        _lo, _hi = None, None
    _ex = os.environ.get('AZEL_TEXT_EXCEPT')
    _text_except = set(x.strip() for x in _ex.split(',')) if _ex else set()
    if _text_except:
        print('⚠AZEL_TEXT_EXCEPT — 이 모듈만 원문 유지: %s' % ', '.join(sorted(_text_except)))
    _to = os.environ.get('AZEL_TEXT_ONLY')
    _text_only = set(x.strip() for x in _to.split(',')) if _to else None
    if _text_only:
        print('⚠AZEL_TEXT_ONLY — 이 모듈에만 번역을 넣는다: %s' % ', '.join(sorted(_text_only)))
    # ★★2026-08-15 실기: 「파일런 룸3」·「기록」 같은 짧은 문자열이 통째로
    #   공백으로 지워져 있었다. 원인은 **앞 문자열의 예산이 뒤 문자열을 먹는 것**이다.
    #     FLD_C8 0x014FA2 `パイロンルーム2` bud=25 (실제 17B)
    #     FLD_C8 0x014FB3 `パイロンルーム3`            ← 앞 자리 패딩이 8B 덮어씀
    #   예전엔 「겹치면 바깥만 남긴다」로 안쪽 쓰기를 버렸는데, 그러면 안쪽
    #   문자열이 **앞 문자열의 패딩 공백에 지워진다**. 버릴 게 아니라
    #   **바깥 예산을 안쪽 시작 직전까지 잘라야** 둘 다 산다.
    #   ⚠예산 > 실제 길이 자체는 정상이다(고정 슬롯 배열). 겹칠 때만 자른다.
    cap_at = {}
    for _pls in places_by_id.values():
        for _p in _pls:
            _fn = {'MOVIE': 'MOVIE.DAT', 'MENUBK': 'MENUBK.BIN',
                   'COMMON': 'COMMON.DAT'}.get(_p[1], _p[2] + '.PRG')
            cap_at.setdefault(_fn, []).append(int(_p[4], 16))
    # ★★2026-08-15 실기 크래시: 캐러밴 상인에게 두 번째로 말을 걸면 「거래한다」 창이
    #   뜨려는 순간 «FILE NOT FOUND:» 로 죽었다. 원인은 위와 같은 «먹힘»인데 먹힌 게
    #   문자열이 아니라 **음성 파일명**이었다 — `TWN_CARA 0x00A526` 의 패딩이
    #   `T_BK_301.PCM\0` 을 통째로 덮어, 스크립트가 그 대사의 음성을 로드하다 실패했다.
    #   파일명은 places 에 없으니 «다음 자리»로만 자르는 위 규칙에 안 걸린다.
    #   → **파일명 꼴 ASCII 의 시작점도 자르기 상한으로 넣는다.**
    #   [[feedback_budget_eats_next_string]] · [[feedback_ascii_string_misread_as_glyph]]
    import re as _re
    _NAME_RE = _re.compile(rb'[A-Z0-9_]{2,8}\.[A-Z]{3}\x00')
    _n_name = 0
    for _fn in list(cap_at):
        _src = os.path.join('work', 'uniq', _fn)
        if not os.path.exists(_src):
            continue
        _d = open(_src, 'rb').read()
        _hits = [m.start() for m in _NAME_RE.finditer(_d)]
        cap_at[_fn].extend(_hits)
        _n_name += len(_hits)
    if _n_name:
        print('   파일명 보호 지점 %d개를 자르기 상한에 추가' % _n_name)
    for _fn in cap_at:
        cap_at[_fn] = sorted(set(cap_at[_fn]))
    import bisect as _bisect

    # ★자르기의 **하한은 «원문 실제 길이»** 다. 다음 «자리»가 원문 한가운데서
    #   시작하는 거짓 검출일 때(TWN_CARA 0x017C5D), 그걸로 자르면 진짜 문자열이
    #   1바이트 잘려 예산 초과가 난다. 표는 `tools/fnt_reserved.py` 가 만든다.
    real_len = {}
    if os.path.exists('work/str_len.tsv'):
        with open('work/str_len.tsv', encoding='utf-8') as f:
            f.readline()
            for line in f:
                c = line.rstrip('\n').split('\t')
                if len(c) == 3:
                    real_len[(c[0], int(c[1], 16))] = int(c[2])
    else:
        print('⚠work/str_len.tsv 가 없다 — fnt_reserved.py 를 먼저 돌릴 것')

    def place_budget(p, uid):
        fn = {'MOVIE': 'MOVIE.DAT', 'MENUBK': 'MENUBK.BIN',
              'COMMON': 'COMMON.DAT'}.get(p[1], p[2] + '.PRG')
        off = int(p[4], 16)
        offs = cap_at[fn]
        j = _bisect.bisect_right(offs, off)
        b = budget[uid]
        if j < len(offs):
            b = max(real_len.get((fn, off), 0), min(b, offs[j] - off))
        return b

    patch = {}
    n = 0
    blocked = 0
    clipped = 0
    fails = []
    for uid, ko in ko_by_id.items():
        for p in places_by_id.get(uid, ()):
            cmap = dict(base_map)
            cmap.update(scene_used.get(p[3], {}))
            pb = place_budget(p, uid)
            if pb < budget[uid]:
                clipped += 1
            _key = (p[2], int(p[4], 16))
            try:
                blob = enc.encode(ko, cmap, pb,
                                  allow1b=(uid not in no1b
                                           and _key not in FORCE_2BYTE_PLACES),
                                  pad_center=(uid in center_pad),
                                  keep2b=(_key in KEEP_2BYTE_PLACES))
            except enc.Budget as e:
                if os.environ.get('AZEL_FORCE'):
                    break          # 실험 중엔 그 자리만 건너뛴다
                fails.append((uid, ko, pb, str(e)))
                break
            # ★2026-08-15 원인 절개용: `AZEL_TEXT_ONLY` 에 모듈 이름을 쉼표로 주면
            #   그 모듈에만 번역을 넣는다. 나머지는 원문 그대로 둔다.
            if _text_only is not None and p[2] not in _text_only:
                continue
            if p[2] in _text_except:
                continue
            if (p[2], int(p[4], 16)) in BLOCKED_PLACES:
                blocked += 1
                continue
            if _lo is not None and not (_lo <= int(p[4], 16) < _hi):
                continue
            fname = {'MOVIE': 'MOVIE.DAT', 'MENUBK': 'MENUBK.BIN',
                     'COMMON': 'COMMON.DAT'}.get(p[1], p[2] + '.PRG')
            patch.setdefault(fname, {})[int(p[4], 16)] = blob
            n += 1
    if fails:
        inv = {v: k for k, v in id_of.items()}
        with open('work/fails.tsv', 'w', encoding='utf-8', newline='') as f:
            f.write('budget\tneed\twhy\tjp\tko\n')
            for uid, ko, b, msg in fails:
                m = re.match(r'예산 초과 (\d+) > (\d+)', msg)
                need = m.group(1) if m else ''
                why = '예산' if m else '슬롯'
                f.write('%d\t%s\t%s\t%s\t%s\n'
                        % (b, need, why, inv.get(uid, ''), ko))
        print('★예산 초과 / 슬롯 없음 %d건 → work/fails.tsv' % len(fails))
        for uid, ko, b, msg in fails[:15]:
            print('   %-34s %s' % (ko[:32], msg[:60]))
        raise SystemExit(1)
    if clipped:
        print('다음 문자열을 침범하던 예산 %d곳을 잘라 썼다' % clipped)
    print('인코딩 OK — 전부 원문 길이에 맞음. 교체 %d곳 / 파일 %d개' % (n, len(patch)))
    if blocked:
        print('⛔코드 자리라 제외한 배치 %d곳 (BLOCKED_PLACES)' % blocked)

    # ★2026-08-15 원인 절개용: `AZEL_NO_TEXT=1` 이면 **텍스트 교체를 전부 버리고**
    #   폰트만 굽는다. 「증상이 텍스트 탓이냐 폰트 탓이냐」를 빌드 한 번으로 가른다.
    #   (글리프 배정 계산은 그대로 두어야 폰트 내용이 정상 빌드와 같아진다.)
    if os.environ.get('AZEL_NO_TEXT'):
        print('⚠AZEL_NO_TEXT — 텍스트 교체 %d곳을 버린다(폰트만 굽는다)' % n)
        patch.clear()

    # --- 2) 폰트 굽기 ----------------------------------------------------
    font = krglyph.load('Galmuri11')
    blank = b'\x00' * 32
    cd = patch.setdefault('COMMON.DAT', {})
    for c, idx in base_used.items():
        g = krglyph.glyph(font, c)
        if g is None:
            raise SystemExit('글리프 없음: %r' % c)
        cd[BASE_OFF + idx * 32] = g
    cd[BASE_OFF + pad1 * 32] = blank
    nf = 0
    for fn, m in scene_used.items():
        fp = patch.setdefault(fn + '.FNT', {})
        for c, idx in m.items():
            fp[18 + (idx - 256) * 32] = krglyph.glyph(font, c)
            nf += 1
    print('폰트: 기본 %d글자 + 장면FNT %d글리프(%d파일)'
          % (len(base_used), nf, len(scene_used)))
    # --- 2.5) 아이템 이름표 ------------------------------------------------
    # ★이 표는 «반각 JIS X0201» 이라 글리프 인덱스 스트림이 아니다.
    #   렌더러가 코드에 박힌 상수로 바꾼다(영문 +125 / 숫자 −46 / 반각가나 −0x5E).
    #   그래서 영문·숫자로 쓰면 **폰트를 새로 구울 필요가 전혀 없다** —
    #   A~Z·0~9 글리프는 원본 그대로 남는 칸이다.
    #   ⛔공백(0x20)은 원본 이름표에 한 번도 안 쓰였다 = 렌더 결과 미검증.
    #     쓰지 말 것(`ぎ` 로 나올 위험).
    if os.path.exists(ITEMS_TSV):
        _, irows = load_tsv(ITEMS_TSV)
        cd = patch.setdefault('COMMON.DAT', {})
        n_item = 0
        for r in irows:
            if len(r) < 5 or not r[4]:
                continue
            off, room, name = int(r[0], 16), int(r[3]), r[4]
            bad = [c for c in name if c not in ITEM_OK]
            if bad:
                raise SystemExit('아이템 이름에 검증 안 된 문자 %r: %s'
                                 % (''.join(bad), name))
            blob = name.encode('ascii') + b'\x00'
            if len(blob) > room:
                raise SystemExit('아이템 이름 자리 초과 %d>%d: %s'
                                 % (len(blob), room, name))
            # ★바이트가 맞아도 «화면 폭»에서 잘린다 — 이름칸은 8글자다.
            #   원본은 탁점(`ﾞ`)이 앞 글자와 합쳐져 바이트보다 짧게 그려지므로
            #   바이트 예산만 보면 넉넉해 보인다. 실기에서 `SHELLPLATE` 가
            #   `SHELLPLAT` 로 잘렸다(9자는 수량 `x` 에 딱 붙는다).
            if len(name) > ITEM_WIDTH:
                raise SystemExit('아이템 이름 화면 폭 초과 %d>%d: %s'
                                 % (len(name), ITEM_WIDTH, name))
            cd[off] = blob.ljust(room, b'\x00')
            n_item += 1
        print('아이템 이름 %d개 (반각 이름표, 폰트 변경 없음)' % n_item)

    # --- 3) 겹치는 쓰기 «남았는지» 확인 -----------------------------------
    # ★예전 정책은 「겹치면 바깥만 남긴다」였는데, 그러면 안쪽 문자열이
    #   바깥의 패딩 공백에 지워진다(실기: 「파일런 룸3」·「기록」이 사라졌다).
    #   이제 위에서 **바깥 예산을 안쪽 시작 직전까지 잘라** 둘 다 살린다.
    #   여기 걸리는 게 있으면 그 자르기가 안 먹은 것이므로 **버그다.**
    drop = 0
    for fname, edits in patch.items():
        keep = {}
        end = -1
        for o in sorted(edits):
            if o < end:
                drop += 1
                continue
            keep[o] = edits[o]
            end = o + len(edits[o])
        patch[fname] = keep
    if drop:
        print('★겹치는 쓰기가 %d곳 남았다 — 예산 자르기가 안 먹었다' % drop)
    return patch


# ★이름 입력 화면 격자가 «화면에서 읽는 순서»대로 쓰는 기본폰트 index.
#   히라가나·가타카나 두 페이지, 열 우선(위→아래, 왼→오른쪽). 영어 페이지는 안 건드린다.
#   [[project_azel_kr]] 세션7 — 격자는 18열×5행. KEEP(`・`71·`ー`65)·미배정은 저절로 빠진다.
_HIRA = ['あいうえお', 'かきくけこ', 'さしすせそ', 'たちつてと', 'なにぬねの',
         'はひふへほ', 'まみむめも', 'や_ゆ_よ', 'らりるれろ', 'わ_を_ん',
         'ぁぃぅぇぉ', 'っゃゅょ_', 'がぎぐげご', 'ざじずぜぞ', 'だぢづでど',
         'ばびぶべぼ', 'ぱぴぷぺぽ', '・ー___']
_KATA = ['アイウエオ', 'カキクケコ', 'サシスセソ', 'タチツテト', 'ナニヌネノ',
         'ハヒフヘホ', 'マミムメモ', 'ヤ_ユ_ヨ', 'ラリルレロ', 'ワ_ヲ_ン',
         'ァィゥェォ', 'ッャュョ_', 'ガギグゲゴ', 'ザジズゼゾ', 'ダヂヅデド',
         'バビブベボ', 'パピプペポ', 'ヴ・ー__']


def name_grid():
    """격자가 화면 읽는 순서대로 쓰는 «원본» 기본폰트 index 열."""
    import basemap as _bm
    rev = {}
    for i in range(256):
        c = _bm.ch(i)
        if c and c not in rev:
            rev[c] = i
    out = []
    for lay in (_HIRA, _KATA):
        for col in lay:
            for ch in col:
                if ch == '_':
                    continue
                i = rev.get(ch)
                if i is not None and i not in out:
                    out.append(i)
    return out


def _sortkey(c):
    """받침 없는 음절 먼저(가갸거겨), 그 다음 받침 있는 음절, 기호는 맨 뒤."""
    if '가' <= c <= '힣':
        return (0 if (ord(c) - 0xAC00) % 28 == 0 else 1, c)
    return (2, c)


def reorder_for_name_entry(base_used, mode=None, pinned=()):
    """격자 칸에 한글을 «받침없음 우선 + 가나다순»으로 재배정한다.

    mode='safe'  1바이트 index(0x20~0x7F)와 나머지를 **각각** 정렬.
                 어느 글자가 1바이트를 쓰는지 안 바뀌므로 **예산 영향 0**.
                 대신 화면에서 두 벌로 토막난다.
    mode='full'  화면 읽는 순서 = 한 벌 정렬. 1바이트 배정이 통째로 바뀌어
                 **예산이 흔들린다** — 반드시 --dry 로 재어 보고 쓸 것.
    mode='off'   재배정 안 함.
    """
    mode = mode or os.environ.get('AZEL_NAMEORDER', 'safe')
    if mode == 'off':
        return base_used
    # ★★2026-08-15: `pinned` 글자는 **index 를 바꾸면 안 된다.**
    #   지명 상자는 기본폰트 앞쪽(index<0x98)만 VRAM 에 올리는데, 여기서
    #   가나다순으로 다시 섞으면 그 글자가 뒤쪽 index 로 밀려 화면이 깨진다
    #   (실기: 「카라반」이 「가 라반」으로 나왔다).
    pinned = set(pinned)
    rev = {v: k for k, v in base_used.items() if k not in pinned}
    slots = [i for i in name_grid() if i in rev]
    out = dict(base_used)
    # ★★재배정은 «같은 index 집합 안의 순열»이어야 한다. 그룹 전체에서 글자를
    #   뽑아 격자에만 꽂으면, 원래 격자에 있던 글자가 제 index 를 들고 남아
    #   **두 글자가 같은 index** 를 가리킨다 → 되읽기에서 「걸」이 「직」으로 나온다.
    if mode == 'full':
        groups = [(slots + [i for i in sorted(rev) if i not in set(slots)], None)]
    else:
        groups = []
        for one in (True, False):
            sg = [i for i in slots if (0x20 <= i < 0x80) == one]
            rest = [i for i in sorted(rev)
                    if (0x20 <= i < 0x80) == one and i not in set(sg)]
            groups.append((sg + rest, None))
    for idxs, _ in groups:
        chars = sorted((rev[i] for i in idxs), key=_sortkey)
        for i, c in zip(idxs, chars):
            out[c] = i
    if len(set(out.values())) != len(out):
        raise SystemExit('★재배정이 순열이 아니다 — index 충돌')
    print('이름입력 격자 %d칸 재배정 (mode=%s)' % (len(slots), mode))
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    dry = '--dry' in sys.argv
    patch = build_patch()
    if dry:
        for f in sorted(patch):
            print('   %-14s %d곳' % (f, len(patch[f])))
        return

    # --- 4) 디스크 쓰기 --------------------------------------------------
    import shutil
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copyfile(src, dst)
    iso = Iso(dst)
    ents = {p.lstrip('/'): (l, s) for p, l, s in iso.walk() if not p.endswith('/')}
    fh = open(dst, 'r+b')
    touched = set()
    for fname, edits in patch.items():
        if fname not in ents:
            print('  ★디스크에 없음:', fname)
            continue
        lba, size = ents[fname]
        data = bytearray(iso.read(lba, size))
        for off, blob in edits.items():
            data[off:off + len(blob)] = blob
        for i in range(0, size, DATA_LEN):
            sec = lba + i // DATA_LEN
            chunk = bytes(data[i:i + DATA_LEN]).ljust(DATA_LEN, b'\x00')
            fh.seek(sec * SECTOR)
            raw = bytearray(fh.read(SECTOR))
            if raw[DATA_OFF:DATA_OFF + DATA_LEN] == chunk:
                continue
            raw[DATA_OFF:DATA_OFF + DATA_LEN] = chunk
            raw = bytearray(cdrom_ecc.recalc_sector(bytes(raw)))
            fh.seek(sec * SECTOR)
            fh.write(bytes(raw))
            touched.add(sec)
    fh.close()
    print('섹터 %d개 갱신 (EDC/ECC 재계산) → %s' % (len(touched), dst))


if __name__ == '__main__':
    main()

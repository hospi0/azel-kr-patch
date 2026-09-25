# -*- coding: utf-8 -*-
"""번역 대상 텍스트의 «단일 진입점» — PRG + MOVIE.DAT 를 한 모델로 모은다.

각 항목:
    src      'PRG' | 'MOVIE'
    module   PRG 이름 또는 무비 이름
    fnt      그 항목이 쓰는 장면 FNT 이름 (없으면 '')
    off      파일 안 오프셋
    budget   덮어쓸 수 있는 바이트 수 (종단 포함). 슬롯 항목이면 슬롯 크기,
             아니면 원문 길이 — §7.25 결론에 따라 **원문 길이를 넘기지 않는다**
    kind     dialog | narration | slot | ui | draft | asset | movie
    toks     토큰열
    text     사람이 읽는 원문
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import census
import fnt as fntmod
import fntmap
import movie as moviemod
import regions
import slots
import strtab

UI_MODULES = {'MENUEN', 'MENUBK', 'MENU', 'ITEM', 'SHOP', 'SAVE', 'FLAGEDIT',
              'WORLD', 'WORLDMAP', 'SNDTEST', 'TITLE', 'CHANGE'}


def render(toks, scene):
    s = []
    for k, v in toks:
        if k in ('g', 'g1'):
            if v >= 256:
                s.append(scene[v - 256] if scene and v - 256 < len(scene)
                         else '【%d】' % (v - 256))
            else:
                s.append(basemap.ch(v))
        elif k == 'c':
            s.append('\\n' if v == 0x06 else '<%02X>' % v)
        else:
            s.append('<!%02X>' % v)
    return ''.join(s)


def _pick(cand, tab):
    """글리프 수가 같은 FNT 후보가 여럿이면, 렌더 결과가 «가나 사이에 한자»로
    자연스러운 쪽을 고른다. 잘못된 폰트를 쓰면 한자가 문맥과 따로 논다.
    (COMMON.DAT 메뉴 구간에서 MENU / EVT043 / EVT134_1 이 전부 31글리프였다.)"""
    if not cand:
        return None
    # `EVT*` 는 무비 전용 폰트다(MOVIE.PRG 의 CPK 목록과 1:1). PRG·COMMON.DAT 가
    # 쓸 리 없으므로 다른 후보가 있으면 먼저 뺀다 — 안 빼면 글리프 수가 같다는
    # 이유만으로 EVT043 이 뽑혀 「性能を見る」가 「性顔を少る」로 읽힌다.
    non_evt = [k for k in cand if not k.startswith('EVT')]
    if non_evt:
        cand = non_evt
    if len(cand) == 1:
        return cand[0]
    best, score = None, -1
    for k in cand:
        sc = fntmap.load(k)
        s = 0
        for _, _, t in tab:
            txt = ''.join(sc[v - 256] if v >= 256 and v - 256 < len(sc)
                          else basemap.ch(v)
                          for kk, v in t if kk in ('g', 'g1'))
            # 「◯◯の」「◯◯を」「◯◯する」 처럼 한자 뒤에 조사가 붙으면 가점
            for i, c in enumerate(txt[:-1]):
                if '一' <= c <= '鿿' and txt[i + 1] in 'のをがはにでする':
                    s += 1
        if s > score:
            best, score = k, s
    return best


def _region_key(data, a, b, nmax):
    """구간의 내용을 «문자열 생바이트열» 로 요약한다 — 구간 경계가 모듈마다
    조금씩 달라도 같은 내용이면 같은 키가 나오게."""
    tab, _ = strtab.parse_table(data, a, nmax, lenient=True)
    return tuple(raw for o, raw, _ in tab if o < b and raw)


def shared_region_fonts(d, fonts, maxf):
    """★PRG 도 «구간마다» 폰트가 다르다 — `COMMON.DAT` 에서 겪은 함정의 재판.

    증거: 마을 모듈(`TWN_*`) 끝에 붙은 «줄거리» 구간과 «상점» 구간은 여러
    모듈에 **바이트 단위로 똑같이** 들어 있다. 그런데 모듈 자체 FNT 로 읽으면
    모듈마다 한자가 달라진다(가나는 같다). 공유 데이터가 모듈 폰트를 쓸 리
    없으므로 자체 FNT 는 틀렸다 — 「広場ではクレイメンが待っていたが」가
    EVTCAMP 로는 「□発ではクレイメンが荷っていたが」로 나왔다.

    그런 구간은 «최대 index+1 == 글리프 수» 인 폰트로 읽는다
    (줄거리 = `EVEEXPL` 185, 상점 = `SHOP` 19).

    ⛔글리프 수 일치만으로 고르면 안 된다 — `TWN_CARA` 첫 구간은 mx+1=92 라
      `FLD_C2` 가 딱 맞지만 읽어보면 「たき外が探えている」로 깨진다(정답은
      자체 FNT `EVTCARA` = 「たき火が燃えている」). **공유 구간일 때만**
      후보 검색으로 넘어가야 한다.

    반환 {(모듈, 구간시작): FNT이름}
    """
    seen = {}
    prgs = sorted(f for f in os.listdir(d) if f.endswith('.PRG'))
    for p in prgs:
        stem = p[:-4]
        own = census.pair_of(stem, fonts)
        # ★구간 탐색 기준(nmax)은 «자체 폰트» 그대로 둔다. 넓히면 구간 경계가
        #   달라져 모집단 자체가 바뀐다 — 여기서 고치려는 건 «어느 폰트로 읽나»
        #   뿐이다.
        nmax = 256 + (fonts[own] if own else maxf)
        data = open(os.path.join(d, p), 'rb').read()
        for a, b, _, _, _ in regions.find(data, nmax):
            key = _region_key(data, a, b, nmax)
            if key:
                seen.setdefault(key, []).append((stem, a, own))

    override = {}

    # ★★ ①「자체 FNT 로는 **불가능한** 구간」 — 내용 대조보다 강한 증거.
    #   구간이 쓰는 최대 글리프 index 가 자체 FNT 글리프 수를 넘으면 그 폰트일 리가 없다.
    #   ⚠아래 ②(내용 대조)만으로는 이걸 못 잡는다 — 구간 «키»를 자체 nmax 로 만드는데,
    #     폰트가 작은 모듈은 범위를 넘는 index 에서 파싱이 끊겨 구간이 짧게 잘리고,
    #     그래서 같은 바이트열인데도 키가 달라져 그룹이 안 된다.
    #     실제로 `TWN_EXCA`(자체 74글리프)·`TWN_RUIN`(36)의 줄거리가 그렇게 새어
    #     「発掘を所隊するが長い儀を待けている」로 읽혔다(정답 = 「隊長を発見するが
    #     深い傷を受けている」, `EVEEXPL` 185글리프). 바이트는 `TWN_E011` 과 **완전 동일**.
    wide = {}
    for p in prgs:
        stem = p[:-4]
        own = census.pair_of(stem, fonts)
        if not own:
            continue
        data = open(os.path.join(d, p), 'rb').read()
        wide[stem] = regions.find(data, 256 + maxf)
        for a, b, _, _, _ in regions.find(data, 256 + fonts[own]):
            w = [(x, y) for x, y, *_ in wide[stem] if x <= a < y]
            if not w:
                continue
            wa, wb = w[0]
            tab, _ = strtab.parse_table(data, wa, 256 + maxf, lenient=True)
            mx = max((v for o, _, t in tab if o < wb
                      for k, v in t if k == 'g' and v >= 256), default=255)
            need = mx - 256 + 1
            if need <= fonts[own]:
                continue                  # 자체 FNT 로 가능하면 손대지 않는다
            cand = [k for k, v in fonts.items() if v == need and fntmap.load(k)]
            if len(cand) == 1:
                override[(stem, a)] = cand[0]

    # ② 내용 대조 — 같은 바이트열이 자체 FNT 가 다른 모듈들에 들어 있을 때
    for key, lst in seen.items():
        if len({own for _, _, own in lst}) < 2:
            continue                      # 자체 FNT 가 갈리지 않으면 판단 불가
        mx = -1
        for raw in key:
            i = 0
            while i < len(raw):
                bb = raw[i]
                if bb >= 0x80:
                    # ★lenient 파서는 «미해독 리드바이트»를 1바이트만 먹고 넘어가므로
                    #   raw 가 리드바이트로 끝날 수 있다. 짝이 없으면 그냥 버린다.
                    if i + 1 >= len(raw):
                        break
                    mx = max(mx, (((bb & 0x7F) << 8) | raw[i + 1]) - 256)
                    i += 2
                else:
                    i += 1
        cand = [k for k, v in fonts.items() if v == mx + 1 and fntmap.load(k)]
        if len(cand) != 1:
            continue
        for stem, a, _ in lst:
            override.setdefault((stem, a), cand[0])
    return override


def collect(d):
    """[dict] — 번역 대상 전체."""
    out = []
    fonts = {f[:-4]: len(fntmod.parse(open(os.path.join(d, f), 'rb').read()))
             for f in os.listdir(d) if f.endswith('.FNT')}
    maxf = max(fonts.values())
    override = shared_region_fonts(d, fonts, maxf)

    for p in sorted(f for f in os.listdir(d) if f.endswith('.PRG')):
        stem = p[:-4]
        own = census.pair_of(stem, fonts)
        ownmax = 256 + (fonts[own] if own else maxf)
        data = open(os.path.join(d, p), 'rb').read()
        for a, b, _, _, _ in regions.find(data, ownmax):
            fn = override.get((stem, a), own)
            nmax = 256 + (fonts[fn] if fn else maxf)
            scene = fntmap.load(fn) if fn else None
            tab, _ = strtab.parse_table(data, a, nmax, lenient=True)
            tab = [e for e in tab if e[0] < b]
            arrs = slots.find_slot_arrays(data, tab, a, b)
            live = slots.live_offsets(data, tab, a, b)
            slot_of = {}
            for _, step, _, items, _ in arrs:
                for o in items:
                    slot_of[o] = step
            for o, raw, t in tab:
                if o not in live or not raw:
                    continue
                if not any(k in ('g', 'g1') for k, _ in t):
                    continue
                if strtab.is_asset_name(raw):
                    kind = 'asset'
                elif census.PAIR.get(stem) == 'EVEEXPL':
                    kind = 'draft'
                elif o in slot_of:
                    kind = 'slot'
                else:
                    txt = render(t, scene)
                    kind = ('narration' if txt.startswith('(')
                            else ('ui' if stem in UI_MODULES else 'dialog'))
                out.append(dict(src='PRG', module=stem, fnt=fn or '', off=o,
                                budget=slot_of.get(o, len(raw) + 1),
                                kind=kind, toks=t, raw=raw,
                                text=render(t, scene)))

    # `.PRG` 밖에 있는 텍스트 자산 — 초기 스캔이 확장자로 범위를 못 박아 통째로
    # 놓쳤던 것들이다. 실기 스크린샷 대조로 하나씩 드러났다.
    #   MENUBK.BIN   「ドラゴン乗りの日記」 같은 읽을거리      (짝 MENUBK.FNT)
    #   COMMON.DAT   상주 공통 UI — 아이템 설명, 메뉴 항목   (짝 ITEM.FNT)
    #                ★폰트도 이 파일에 있지만(+0x1068A) 텍스트 구간과 겹치지 않는다.
    # ★파일 하나에 폰트 하나가 아니다. `COMMON.DAT` 는 **구간마다 다른 FNT** 를 쓴다
    #   (0xA760 아이템 설명 = ITEM.FNT / 0xD0D9 메뉴 항목 = MENU.FNT).
    #   ITEM 하나로 읽으면 「性能を見る」가 「性LnをKnる」로 나와 원문을 못 읽는다.
    #   그래서 구간별로 «최대 글리프 index + 1 = FNT 글리프 수»인 폰트를 골라 쓴다.
    for fname, kind in (('MENUBK.BIN', 'ui'), ('COMMON.DAT', 'ui')):
        mb = os.path.join(d, fname)
        if not os.path.exists(mb):
            continue
        data = open(mb, 'rb').read()
        src = fname.split('.')[0]
        for a, b, _, _, _ in regions.find(data, 256 + maxf):
            tab, _ = strtab.parse_table(data, a, 256 + maxf, lenient=True)
            tab = [e for e in tab if e[0] < b]
            mx = max((v - 256 for _, _, t in tab for k, v in t
                      if k in ('g', 'g1') and v >= 256), default=-1)
            cand = [k for k, v in fonts.items()
                    if v == mx + 1 and fntmap.load(k)]
            fkey = cand[0] if len(cand) == 1 else _pick(cand, tab)
            if not fkey:
                continue
            nmax = 256 + fonts[fkey]
            scene = fntmap.load(fkey)
            tab, _ = strtab.parse_table(data, a, nmax, lenient=True)
            tab = [e for e in tab if e[0] < b]
            live = slots.live_offsets(data, tab, a, b)
            for o, raw, t in tab:
                if o not in live or not raw:
                    continue
                if not any(k in ('g', 'g1') for k, _ in t):
                    continue
                out.append(dict(src=src, module=src, fnt=fkey,
                                off=o, budget=len(raw) + 1, kind=kind,
                                toks=t, raw=raw, text=render(t, scene)))

    for name, a, b, recs, tab in moviemod.parse(d):
        scene = fntmap.load(name)
        for o, raw, t in tab:
            if not raw or not any(k in ('g', 'g1') for k, _ in t):
                continue
            out.append(dict(src='MOVIE', module=name, fnt=name, off=o,
                            budget=len(raw) + 1, kind='movie', toks=t, raw=raw,
                            text=render(t, scene)))
    return out

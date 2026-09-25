# -*- coding: utf-8 -*-
"""글리프 슬롯 배정 — 어떤 글자를 기본 폰트에, 어떤 글자를 장면 FNT 에 둘지.

글리프 공간은 두 층이다(§7.7).
    index 0..255   기본 폰트 = COMMON.DAT 상주. **전 모듈 공유**.
                   그중 **0x20~0x7F 는 1바이트 토큰으로 쓸 수 있다** → 예산 절반.
    index 256..    장면별 `.FNT`. 그 모듈에서만.

그래서 배정 원칙:
  1. **가장 자주 쓰는 음절을 기본 폰트의 1바이트 구간(0x20~0x7F)에** 둔다.
     한 글자가 2 B → 1 B 가 되므로 원문 길이 예산에 직접 도움이 된다.
  2. 그다음 빈도는 기본 폰트의 나머지 칸(2바이트지만 모든 모듈이 공유).
  3. 남은 음절은 그 모듈 `.FNT` 에 모듈별로.

원문에서 그대로 둬야 하는 칸(숫자·기호·영문·합자)은 건드리지 않는다 —
번역문에도 `(`, `)`, `…`, `！`, `？`, 숫자가 그대로 쓰인다.
"""
import os
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import basemap

# 기본 폰트에서 «유지»할 index. 나머지는 한글로 갈아끼울 수 있다.
KEEP = set()
for _i, _c in enumerate(basemap.TABLE):
    if _c in '※　 ' or _c in '0123456789' or _c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        KEEP.add(_i)
    elif _c in '…()『』！？ー＋。「」、・％×／=':
        KEEP.add(_i)
    elif len(_c) > 1:            # BP, EXP 합자
        KEEP.add(_i)

# 실험 스위치: 가타카나 글리프를 «원본 그대로» 두고 싶을 때(아이템 이름 조사).
if os.environ.get('AZEL_KEEP_KATAKANA'):
    for _i, _c in enumerate(basemap.TABLE):
        if len(_c) == 1 and 'ァ' <= _c <= 'ヶ':
            KEEP.add(_i)

ONE_BYTE = [i for i in range(0x20, 0x80) if i not in KEEP]
TWO_BYTE = [i for i in range(256) if i not in KEEP and i not in ONE_BYTE]


def base_capacity():
    return len(ONE_BYTE), len(TWO_BYTE)


def allocate(unit_texts, places_by_unit, fnt_sizes):
    """번역문에서 쓰는 글자를 슬롯에 배정한다.

    unit_texts      {unit_id: 번역문}
    places_by_unit  {unit_id: [(module, fnt)]}
    fnt_sizes       {fnt이름: 원래 글리프 수}

    반환 (base_map, scene_map)
      base_map   {글자: index}          전 모듈 공유
      scene_map  {fnt이름: {글자: index}}  index 는 256 부터
    """
    freq = Counter()
    per_fnt = {}
    for uid, txt in unit_texts.items():
        for ch in txt:
            if ch in basemap.REVERSE_KEEP:
                continue
            freq[ch] += len(places_by_unit.get(uid, ()))
        for mod, fn in places_by_unit.get(uid, ()):
            per_fnt.setdefault(fn, Counter()).update(
                c for c in txt if c not in basemap.REVERSE_KEEP)

    base_map = {}
    for ch, _ in freq.most_common(len(ONE_BYTE) + len(TWO_BYTE)):
        slot = ONE_BYTE[len(base_map)] if len(base_map) < len(ONE_BYTE) \
            else TWO_BYTE[len(base_map) - len(ONE_BYTE)]
        base_map[ch] = slot

    scene_map = {}
    for fn, cnt in per_fnt.items():
        rest = [c for c in cnt if c not in base_map]
        scene_map[fn] = {c: 256 + i for i, c in enumerate(sorted(rest))}
    return base_map, scene_map

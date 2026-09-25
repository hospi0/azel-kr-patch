# -*- coding: utf-8 -*-
"""장면별 `.FNT` 글리프 → 한자 판독표 로더.

표는 `data/fnt/<FNT이름>.txt` 에 둔다. 한 줄 16글리프, 공백 구분,
`#` 로 시작하는 줄은 주석. 인덱스 0 = 텍스트 토큰의 (index - 256).

판독은 `tools/fnt_sheet.py` 로 뽑은 확대 시트를 직접 읽어 만든다.
표의 글리프 수는 그 `.FNT` 의 글리프 수와 **반드시 같아야** 한다 —
어긋나면 그 뒤 전부가 밀려 엉뚱한 한자로 읽힌다.
"""
import os

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'data', 'fnt')
_cache = {}


def load(name):
    """FNT 이름(확장자 없이) → [글자, ...] 또는 None."""
    if name in _cache:
        return _cache[name]
    path = os.path.join(DATA, name + '.txt')
    if not os.path.exists(path):
        _cache[name] = None
        return None
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            if line.startswith('#'):
                continue
            out.extend(line.split())
    _cache[name] = out
    return out


def check(name, nglyph):
    """표 길이와 실제 글리프 수가 맞는지. (ok, 표길이)"""
    t = load(name)
    if t is None:
        return None, 0
    return len(t) == nglyph, len(t)

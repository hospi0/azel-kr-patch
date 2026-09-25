# -*- coding: utf-8 -*-
"""남은 원문이 «화면을 깨뜨리는지»를 폰트 칸으로 판정한다.

  python tools/leftover_risk.py <무수정원본Track1> <빌드본Track1>

★「글자냐 그림이냐」를 폰트 슬롯으로 가르듯([[feedback_font_slot_reuse_disproves_render]]),
  「미번역이 위험한가」도 **그 문자열이 쓰는 글리프 칸이 한글로 덮였는가**로 갈린다.

  - 기본폰트(0~255) 만 쓰는 미번역   → 원문 가나 그대로 나온다. 보기 흉할 뿐.
  - 자체 `.FNT` 칸을 쓰는데 **그 칸이 덮였다** → 「으모모」처럼 **쓰레기**가 된다.
    [[feedback_font_reuse_untranslated_looks_scrambled]] / [[feedback_embedded_font_no_spare_slots]]

모듈이 어느 FNT 를 쓰는지는 **원본↔빌드 FNT 차분**으로 확인한다 — 덮인 칸만
비교하면 되므로 폰트 오배정 문제를 우회한다.
"""
import os
import struct
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import find_uncovered as FU
from iso9660 import Iso

SKIP = ('.EPK', '.CGB')


def repainted(fa, fb):
    """FNT 원본↔빌드 → 한글로 덮인 글리프 index 집합(256+i)."""
    if len(fa) < 18 or len(fa) != len(fb):
        return None
    n, tag = struct.unpack_from('>HH', fa, 0)
    if tag != 4 or not 0 < n < 4000:
        return None
    out = set()
    for i in range(n):
        s = 18 + i * 32
        if fa[s:s + 32] != fb[s:s + 32]:
            out.add(256 + i)
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    a, b = Iso(src), Iso(dst)
    ents = {p.lstrip('/'): (l, s) for p, l, s in a.walk() if not p.endswith('/')}

    # ① 덮인 칸 — 디스크 전체 FNT 를 합친다(모듈↔FNT 대응을 안 믿는다)
    hit_any = set()
    per_fnt = {}
    for name in sorted(ents):
        if not name.upper().endswith('.FNT'):
            continue
        fa = a.read(*ents[name])
        fb = b.read(*ents[name])
        r = repainted(fa, fb)
        if r:
            per_fnt[name] = r
            hit_any |= r
    print('# FNT %d개에서 덮인 칸 — 합집합 %d개' % (len(per_fnt), len(hit_any)))

    # ② 남은 원문이 그 칸을 쓰나
    risky = defaultdict(list)
    safe = 0
    for name in sorted(ents):
        u = name.upper()
        if u.endswith(SKIP) or u.endswith('.FNT'):
            continue
        da = a.read(*ents[name])
        db = b.read(*ents[name])
        if da == db:
            continue
        # 그 모듈이 쓰는 FNT = 이름이 겹치는 것 + 전체 합집합(보수적)
        for s, e, sh in FU.shapes_in(da):
            if da[s:e] != db[s:e]:
                continue
            g = [x for x in sh if x != 'c']
            if len(g) < 2:
                continue
            used = {x for x in sh if x == '*'}
            if not used:
                safe += 1
                continue
            # 실제 index 를 다시 뽑는다
            idx = []
            i = s
            while i < e:
                x = da[i]
                if x >= 0x80:
                    idx.append(((x & 0x7F) << 8) | da[i + 1])
                    i += 2
                else:
                    i += 1
            bad = [v for v in idx if v >= 256 and v in hit_any]
            if bad:
                risky[name].append((s, e - s, sorted(set(bad))[:8], len(idx)))
            else:
                safe += 1

    tot = sum(len(v) for v in risky)
    print('== 폰트 칸을 쓰면서 «덮인 칸»에 걸리는 미번역 %d곳 / 안전 %d곳' % (tot, safe))
    for name in sorted(risky):
        print('# %s — %d곳' % (name, len(risky[name])))
        for s, ln, bad, n in risky[name][:25]:
            print('   %06X len=%-4d 글자%-3d 덮인칸 %s' % (s, ln, n, bad))


if __name__ == '__main__':
    main()

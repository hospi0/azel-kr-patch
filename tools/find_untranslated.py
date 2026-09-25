# -*- coding: utf-8 -*-
"""번역표가 «건드리지 않는» 텍스트를 찾아낸다 — 미번역 검출.

  python tools/find_untranslated.py [work/uniq] > work/untrans.tsv

원리
  `work/trans/places.tsv` = 빌더가 실제로 덮어쓰는 모든 자리(파일·오프셋·길이).
  그 밖에서 «일본어로 읽히는 널종단 문자열»이 나오면 그건 미번역이다.
  ★검출기(regions.find)가 놓친 구간을 잡는 게 목적이므로, 여기서는
    regions 를 아예 쓰지 않고 **파일 전체를 맹목 스캔**한다.

노이즈 대책 (전부 필요하다 — 하나만 빼도 코드·그래픽이 쏟아진다)
  ① 글리프 토큰이 4개 이상이고 제어코드 잡음이 없을 것
  ② 기본폰트 index 가 «가나» 범위인 비율이 절반 이상일 것
     (SH-2 코드 안 ASCII 데이터는 1바이트 토큰 비율이 높다 → 따로 뺀다)
  ③ 파일명(`*.PCM` 등)은 제외
  ④ 이미 덮어쓰는 자리와 겹치면 제외
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import fnt as fntmod
import fntmap
import strtab

PLACES = 'work/trans/places.tsv'

# 기본 폰트에서 «가나» 인 index 집합 — 판정의 핵심.
KANA = {i for i in range(256)
        if '぀' <= basemap.ch(i) <= 'ヿ'}
PUNCT = {i for i in range(256) if basemap.ch(i) in '、。「」『』！？…（）()・ー'}


def load_places():
    cov = defaultdict(list)
    with open(PLACES, encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) < 7:
                continue
            _id, src, mod, fnt, off, budget, kind = p[:7]
            key = mod if src in ('PRG',) else src
            cov[key].append((int(off, 16), int(budget)))
    return cov


def merge(ranges):
    ranges = sorted(ranges)
    out = []
    for a, n in ranges:
        b = a + n
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def covered(iv, a, b):
    """[a,b) 가 병합된 구간 목록 iv 와 겹치나."""
    lo, hi = 0, len(iv)
    while lo < hi:
        m = (lo + hi) // 2
        if iv[m][1] <= a:
            lo = m + 1
        else:
            hi = m
    return lo < len(iv) and iv[lo][0] < b


def scan_file(data, nmax, iv, scene):
    """파일 전체를 맹목 스캔해 미번역 후보를 낸다."""
    out = []
    n = len(data)
    i = 0
    while i < n:
        if data[i] < 0x80:
            i += 1
            continue
        # 여기서부터 널종단까지 토큰화해 본다
        tab, _ = strtab.parse_table(data, i, nmax, lenient=False)
        if not tab:
            i += 1
            continue
        o, raw, toks = tab[0]
        end = o + len(raw) + 1
        i = end if len(raw) else i + 1
        if not raw or strtab.is_asset_name(raw):
            continue
        g = [v for k, v in toks if k in ('g', 'g1')]
        g1 = [v for k, v in toks if k == 'g1']
        if len(g) < 4:
            continue
        if len(g1) > len(g) * 0.3:        # SH-2 코드 안 ASCII 데이터
            continue
        base = [v for v in g if v < 256]
        kana = sum(1 for v in base if v in KANA or v in PUNCT)
        if not base or kana < len(base) * 0.6:
            continue
        if kana < 3:
            continue
        if covered(iv, o, end):
            continue
        txt = ''.join(
            (scene[v - 256] if scene and v - 256 < len(scene) else '【%d】' % (v - 256))
            if v >= 256 else basemap.ch(v)
            for v in g)
        out.append((o, len(raw) + 1, txt))
    return out


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else 'work/uniq'
    cov = load_places()
    fonts = {f[:-4]: len(fntmod.parse(open(os.path.join(d, f), 'rb').read()))
             for f in os.listdir(d) if f.endswith('.FNT')}
    maxf = max(fonts.values())

    import census
    print('file\toffset\tlen\ttext')
    tot = 0
    for fn in sorted(os.listdir(d)):
        if not (fn.endswith('.PRG') or fn.endswith('.DAT') or fn.endswith('.BIN')):
            continue
        stem = fn.split('.')[0]
        data = open(os.path.join(d, fn), 'rb').read()
        own = census.pair_of(stem, fonts) if fn.endswith('.PRG') else None
        scene = fntmap.load(own) if own else None
        nmax = 256 + (fonts[own] if own else maxf)
        iv = merge(cov.get(stem, [])) or []
        for o, ln, txt in scan_file(data, nmax, iv, scene):
            print('%s\t%06X\t%d\t%s' % (stem, o, ln, txt))
            tot += 1
    print('# 합계 %d' % tot, file=sys.stderr)


if __name__ == '__main__':
    main()

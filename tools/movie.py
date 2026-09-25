# -*- coding: utf-8 -*-
"""`MOVIE.DAT` — 무비 자막. 무비별 블록으로 나누고 짝 FNT 를 찾는다.

  python tools/movie.py work/uniq [출력.tsv]

`.PRG` 만 스캔하다가 통째로 놓쳤던 자산이다. 내용은 PRG 와 같은 글리프 인덱스
스트림이지만, **무비마다 다른 `EVTxxx.FNT` 를 쓴다**.

블록 경계 찾기: `.FNT` 는 그 장면 텍스트의 **첫등장 순서** 배열이므로, 한 블록 안에서
index ≥ 256 의 첫등장은 256, 257, 258 … 로 이어진다. **그 순번이 256 으로 리셋되는
지점이 무비 경계**다.

블록의 FNT 는 «그 블록이 쓰는 최대 index + 1 = FNT 글리프 수»로 후보를 잡고,
판독표로 렌더해 말이 되는지 확인한다(`EVT008` 은 `[0]=隊 [1]=長` 이라
첫 문자열이 「隊長！」로 맞아떨어졌다).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import fnt as fntmod
import fntmap
import strtab

NMAX = 256 + 800


TERM = b'\xff\xff\x00\x00\x00\x00\x00\x00'
CUE = 8


def cues(data):
    """[(block_start, text_end, [(start, end, flag, off)])] — 무비 블록 목록.

    구조 (실측):
        [자막 텍스트 문자열들][큐 레코드 8 B × N][FF FF 00 00 00 00 00 00]
    큐 레코드 = BE16 시작프레임, BE16 끝프레임, BE16 플래그(관측값 전부 0x0025),
                BE16 **자막의 파일 절대 오프셋**.
    ★off 를 «블록 상대»로 잘못 보면 첫 블록(0 부터 시작이라 값이 같다)만 맞고
      나머지 블록에서 전부 어긋나, 큐 테이블이 텍스트로 읽혀 「は<0E>…」가 나온다.
    """
    import struct
    out = []
    pos = 0
    while True:
        t = data.find(TERM, pos)
        if t < 0:
            break
        # 종단자 앞에서 8바이트 큐 레코드를 거슬러 올라간다.
        # ★큐 레코드는 3번째 워드가 항상 0x0025 다. 이걸 지표로 삼지 않으면
        #   큐 테이블이 텍스트로 잘못 읽혀 「は<0E>…」 같은 쓰레기가 섞인다.
        i = t
        recs = []
        while i - CUE >= pos:
            s, e, fl, off = struct.unpack_from('>4H', data, i - CUE)
            # off 는 «파일 절대 오프셋»이다(블록 상대가 아니다).
            if fl != 0x0025 or e < s or not (pos <= off < i - CUE):
                break
            recs.insert(0, (s, e, fl, off))
            i -= CUE
        out.append((pos, i, recs))
        pos = t + len(TERM)
    return out


def movie_order(d):
    """MOVIE.PRG 안 CPK 목록 = 무비 순서. 이름이 곧 `.FNT` 이름이다."""
    import re
    raw = open(os.path.join(d, 'MOVIE.PRG'), 'rb').read()
    out = []
    for m in re.finditer(rb'[A-Z0-9_]{3,}\.CPK', raw):
        n = m.group().decode()[:-4]
        if n not in out:
            out.append(n)
    return out


def split_by_movie(data, d):
    """무비 순서를 따라 자막을 나눈다.

    한 무비의 자막은 그 무비 `.FNT` 안 index 만 쓴다. 그러므로 현재 무비 폰트의
    글리프 수를 넘는 index 가 나오면 다음 무비로 넘어간 것이다.
    """
    fonts = {f[:-4]: len(fntmod.parse(open(os.path.join(d, f), 'rb').read()))
             for f in os.listdir(d) if f.endswith('.FNT')}
    order = [n for n in movie_order(d) if n in fonts]
    tab, _ = strtab.parse_table(data, 0, NMAX, lenient=True)

    out = []
    pos = 0
    for name in order:
        if pos >= len(data):
            break
        # ★그 무비 폰트 크기로 «엄격» 파싱한다. 범위를 넘는 index 가 나오는 곳이
        #   정확히 다음 무비의 시작이다. 큰 nmax 로 통째 파싱하면 경계가 안 잡힌다.
        tab, end = strtab.parse_table(data, pos, 256 + fonts[name], lenient=False)
        if tab:
            out.append((name, tab))
            pos = end
    return out, order, fonts


def blocks(data):
    """[(start, end, maxidx, strings)] — 첫등장 순번 리셋으로 나눈 블록."""
    tab, _ = strtab.parse_table(data, 0, NMAX, lenient=True)
    out = []
    cur = []
    seen = set()
    nxt = 256
    start = 0
    for off, raw, toks in tab:
        ids = [v for k, v in toks if k in ('g', 'g1') and v >= 256]
        # ★«첫등장 순번»으로 판정한다. 새 index 는 반드시 nxt 여야 하고,
        #   256 으로 되돌아가면 새 무비가 시작된 것이다.
        #   「256 이 또 나오면 리셋」으로 보면 같은 글자가 반복될 때마다 잘린다.
        reset = any(v == 256 and nxt > 256 and v not in seen for v in ids)
        if reset and cur:
            out.append((start, off, max(seen) if seen else 255, cur))
            cur = []
            seen = set()
            nxt = 256
            start = off
        for v in ids:
            if v not in seen:
                seen.add(v)
                if v >= nxt:
                    nxt = v + 1
        cur.append((off, raw, toks))
    if cur:
        end = cur[-1][0] + len(cur[-1][1]) + 1
        out.append((start, end, max(seen) if seen else 255, cur))
    return out


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


def parse(d):
    """[(movie, start, end, cues, strings)] — 무비별 자막."""
    data = open(os.path.join(d, 'MOVIE.DAT'), 'rb').read()
    order = [n for n in movie_order(d)
             if os.path.exists(os.path.join(d, n + '.FNT'))]
    out = []
    for i, (a, b, recs) in enumerate(cues(data)):
        if i >= len(order):
            break
        name = order[i]
        ng = len(fntmod.parse(open(os.path.join(d, name + '.FNT'), 'rb').read()))
        tab, _ = strtab.parse_table(data, a, 256 + ng, lenient=True)
        tab = [e for e in tab if e[0] < b]
        out.append((name, a, b, recs, tab))
    return out


def main():
    d = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    res = parse(d)
    rows = []
    tot = 0
    print('%-4s %-10s %-17s %6s %6s' % ('#', '무비', '구간', '자막', '글자'))
    for i, (name, a, b, recs, tab) in enumerate(res):
        scene = fntmap.load(name)
        nch = sum(1 for _, _, t in tab for k, _ in t if k in ('g', 'g1'))
        tot += nch
        print('%-4d %-10s 0x%04X..0x%04X %6d %6d' % (i, name, a, b, len(tab), nch))
        for off, raw, toks in tab:
            rows.append((i, name, off, len(raw) + 1, render(toks, scene)))
    print('---- 무비 %d개, 자막 %d개, 글자 %d' % (len(res), len(rows), tot))

    if out:
        with open(out, 'w', encoding='utf-8') as f:
            f.write('movie_no\tmovie\toffset\tbytes\ttext\n')
            for r in rows:
                f.write('%d\t%s\t%06X\t%d\t%s\n' % r)
        print('→', out)


if __name__ == '__main__':
    main()

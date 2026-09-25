# -*- coding: utf-8 -*-
"""글리프 비트맵 → 한자 사전. 이미 판독한 FNT 로 나머지 FNT 를 자동 판독한다.

  python tools/glyphdict.py <추출디렉터리>          # 현황 보기
  python tools/glyphdict.py <추출디렉터리> --emit   # 자동 판독된 표를 data/fnt/ 에 씀

원리: `.FNT` 는 장면별 «한자 서브셋»이라 배열 순서는 제각각이지만,
**같은 글자는 같은 32바이트 비트맵**이다. 그래서 한 번 눈으로 읽어 만든 표
(`data/fnt/EVTZOAH.txt`, 715자)를 비트맵→글자 사전으로 바꾸면
나머지 100개 FNT 의 대부분을 자동으로 채울 수 있다.

기본 폰트(`COMMON.DAT +0x1068A`, 256자)도 사전에 넣는다 — 상용한자 30여 자가
장면 FNT 에도 나올 수 있다.

남는 글리프(사전에 없는 것)만 `tools/fnt_sheet.py` 로 뽑아 눈으로 읽으면 된다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import fnt as fntmod
import fntmap

BASE_OFF = 0x1068A


def build(d):
    """{32바이트 비트맵: 글자} 사전."""
    dic = {}
    common = os.path.join(d, 'COMMON.DAT')
    if os.path.exists(common):
        data = open(common, 'rb').read()
        for i in range(256):
            g = data[BASE_OFF + i * 32: BASE_OFF + (i + 1) * 32]
            c = basemap.TABLE[i]
            if len(c) == 1 and c not in ' 　' and g not in dic:
                dic[g] = c
    # ★사전의 «원본»은 수기 표와 _extra.tsv 뿐이다.
    #   `--emit` 이 만든 자동 생성 표를 다시 사전에 넣으면 파생물이 원본을 덮어써서,
    #   원본을 고쳐도 결과가 안 바뀐다(維 로 고쳤는데 계속 羅 로 나왔다).
    for f in sorted(os.listdir(d)):
        if not f.endswith('.FNT'):
            continue
        name = f[:-4]
        path = os.path.join(fntmap.DATA, name + '.txt')
        if not os.path.exists(path):
            continue
        if '자동 판독' in open(path, encoding='utf-8').readline(200):
            continue
        glyphs = fntmod.parse(open(os.path.join(d, f), 'rb').read())
        ok, _ = fntmap.check(name, len(glyphs))
        if not ok:
            continue
        tab = fntmap.load(name)
        for g, c in zip(glyphs, tab):
            dic.setdefault(g, c)

    # 어느 표에도 없던 고유 글리프를 직접 읽어 채운 목록.
    extra = os.path.join(fntmap.DATA, '_extra.tsv')
    if os.path.exists(extra):
        cache = {}
        with open(extra, encoding='utf-8') as fp:
            for line in fp:
                if line.startswith('#') or not line.strip():
                    continue
                name, idx, ch = line.rstrip('\n').split('\t')
                if name not in cache:
                    p = os.path.join(d, name + '.FNT')
                    if not os.path.exists(p):
                        continue
                    cache[name] = fntmod.parse(open(p, 'rb').read())
                dic.setdefault(cache[name][int(idx)], ch)
    return dic


def main():
    d = sys.argv[1]
    emit = '--emit' in sys.argv
    dic = build(d)
    print('사전 %d개 비트맵' % len(dic))

    tot = known = 0
    rows = []
    for f in sorted(os.listdir(d)):
        if not f.endswith('.FNT'):
            continue
        name = f[:-4]
        glyphs = fntmod.parse(open(os.path.join(d, f), 'rb').read())
        hit = [dic.get(g) for g in glyphs]
        k = sum(1 for x in hit if x)
        tot += len(glyphs)
        known += k
        have, _ = fntmap.check(name, len(glyphs))
        rows.append((name, len(glyphs), k, bool(have)))
        # 자동 생성분은 사전이 갱신되면 다시 써야 한다. 수기 표(헤더에 «자동 판독»이
        # 없는 것)는 절대 덮어쓰지 않는다 — 눈으로 읽은 결과가 유일한 원본이다.
        path = os.path.join(fntmap.DATA, name + '.txt')
        auto = (not os.path.exists(path) or
                '자동 판독' in open(path, encoding='utf-8').readline(200))
        if emit and auto and k:
            with open(path, 'w', encoding='utf-8') as fp:
                fp.write('# %s.FNT — %d글리프, 자동 판독 %d개 (사전 매칭)\n'
                         '# ?  = 사전에 없어 아직 못 읽은 글리프. 시트로 확인해 채울 것.\n'
                         % (name, len(glyphs), k))
                cells = [x if x else '?' for x in hit]
                for i in range(0, len(cells), 16):
                    fp.write(' '.join(cells[i:i + 16]) + '\n')

    rows.sort(key=lambda r: -(r[1] - r[2]))
    print('%-12s %6s %6s %6s  %s' % ('FNT', '글리프', '판독', '미판독', '수기표'))
    for name, n, k, have in rows[:22]:
        print('%-12s %6d %6d %6d  %s' % (name, n, k, n - k, '있음' if have else ''))
    print('---- 글리프 %d개 중 %d개 판독 (%.1f%%), 미판독 %d개'
          % (tot, known, 100.0 * known / tot, tot - known))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""«아는 원문»이 디스크에 남아 있는 자리를 전수 확정한다.

  python tools/find_uncovered.py <무수정원본Track1> <빌드본Track1> [--tsv 출력]

배경 — 실기 스샷의 「으모모」는 미번역 `クルル` 이었다. 번역문 「쿠룰」은 이미
있는데 **그 occurrence 가 빌더 대상에서 빠져** 있었다. 즉 문제는 「모르는 텍스트」가
아니라 **아는 텍스트의 안 덮인 자리**다.

블라인드 스캔은 못 쓴다 — `マ反` 같은 2글자 바이너리가 수백 건 섞인다
([[feedback_scan_coverage_and_detectors]]). 그래서 **모집단과 대조**한다.
대조 열쇠는 폰트에 안 기대는 «골격»:

    글자마다  기본폰트 글자(가나·기호) → 그 index / 자체폰트 글자(한자) → 와일드카드
              제어코드 → 'c'

한자를 와일드카드로 두므로 **모듈마다 FNT 가 달라도 그대로 맞는다**
([[feedback_per_region_font_not_per_file]] 를 우회). 가나 위치·개수가 다 맞아야
하므로 잡음이 우연히 맞을 확률은 사실상 0이다.
"""
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import basemap
from iso9660 import Iso

SKIP = ('.EPK', '.FNT', '.CGB')
TOK = re.compile(r'<!([0-9A-F]{2})>|<([0-9A-F]{2})>|\\n|(.)', re.S)

REV = {}
for _i in range(256):
    _c = basemap.ch(_i)
    if _c and _c not in REV:
        REV[_c] = _i


def shape_of_text(s):
    """번역표의 원문 → 골격. 못 만들면 None."""
    out = []
    for m in TOK.finditer(s):
        raw, ctrl, ch = m.group(1), m.group(2), m.group(3)
        if raw is not None or ctrl is not None or ch is None:
            out.append('c')
        elif ch in REV:
            out.append(REV[ch])
        else:
            out.append('*')               # 자체 폰트 한자 = 와일드카드
    return tuple(out) if out else None


def shapes_in(data):
    """디스크 바이트 → [(시작, 끝, 골격)]"""
    n = len(data)
    i = 0
    while i < n - 1:
        if data[i] < 0x80:
            i += 1
            continue
        s = i
        sh = []
        while i < n:
            b = data[i]
            if b == 0:
                break
            if b >= 0x80:
                if i + 1 >= n:
                    sh = None
                    break
                v = ((b & 0x7F) << 8) | data[i + 1]
                sh.append(v if v < 256 else '*')
                i += 2
            elif b < 0x20:
                sh.append('c')
                i += 1
            else:
                sh.append(b)
                i += 1
        if sh:
            yield s, i, tuple(sh)
        i += 1


def main():
    src, dst = sys.argv[1], sys.argv[2]
    out_tsv = sys.argv[sys.argv.index('--tsv') + 1] if '--tsv' in sys.argv else None

    # ① 모집단 = 번역이 있는 원문
    corpus = {}
    with open('work/trans/ko.tsv', encoding='utf-8') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 2 and p[1] and p[0] != p[1]:
                sh = shape_of_text(p[0])
                # ★★와일드카드만으로 된 골격은 «아무 데나» 맞는다 — 한자만
                #   4글자인 `集中砲火` 하나가 27,218곳에 걸렸다. 고정점(가나·기호)
                #   개수와 비율을 함께 건다. [[feedback_scan_coverage_and_detectors]]
                if not sh:
                    continue
                anchors = [x for x in sh if isinstance(x, int)]
                wild = sum(1 for x in sh if x == '*')
                # 갈래 ① 와일드카드가 «하나도 없으면» 골격 = 정확한 바이트열이다.
                #        (`クルル` 처럼 가나만인 이름) — 3글자부터 안전.
                # 갈래 ② 한자가 섞이면 고정점 수·비율을 함께 건다.
                if wild == 0:
                    if len(anchors) < 3:
                        continue
                elif len(sh) < 5 or len(anchors) < 4 or len(anchors) < len(sh) * 0.4:
                    continue
                corpus.setdefault(sh, (p[0], p[1]))
    print('# 모집단 골격 %d개' % len(corpus))

    a, b = Iso(src), Iso(dst)
    ents = {p.lstrip('/'): (l, s) for p, l, s in a.walk() if not p.endswith('/')}
    rows = []
    for name in sorted(ents):
        if name.upper().endswith(SKIP):
            continue
        lba, size = ents[name]
        da = a.read(lba, size)
        db = b.read(lba, size)
        if da == db:
            continue
        hit = []
        for s, e, sh in shapes_in(da):
            if sh not in corpus:
                continue
            if da[s:e] != db[s:e]:
                continue                  # 이미 번역이 들어갔다
            jp, ko = corpus[sh]
            hit.append((s, e - s, jp, ko))
        if hit:
            print('# %s — %d곳' % (name, len(hit)))
            for s, ln, jp, ko in hit[:200]:
                print('   %06X %3d  %s → %s' % (s, ln, jp[:38], ko[:38]))
            rows += [(name, s, ln, jp, ko) for s, ln, jp, ko in hit]
    print('== 안 덮인 자리 %d곳 / 고유 원문 %d개'
          % (len(rows), len({r[3] for r in rows})))
    if out_tsv:
        with open(out_tsv, 'w', encoding='utf-8', newline='\n') as f:
            f.write('file\toffset\tlen\tjp\tko\n')
            for name, s, ln, jp, ko in rows:
                f.write('%s\t%06X\t%d\t%s\t%s\n' % (name, s, ln, jp, ko))
        print('→ %s' % out_tsv)


if __name__ == '__main__':
    main()

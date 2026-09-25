# -*- coding: utf-8 -*-
"""빌드본에 남은 «모집단에도 없는» 텍스트를 훑어 사람 눈으로 확정할 목록을 만든다.

  python tools/survey_leftover.py <무수정원본Track1> <빌드본Track1>

`find_uncovered.py` 는 **아는 원문**의 안 덮인 자리를 정확히 집는다.
여기서는 그 나머지 — 모집단에 아예 없는 문자열 — 만 남겨 **고유 문안별로 묶어**
보여 준다. 블라인드 스캔이라 잡음이 섞이므로 배제 규칙을 문자열 단위로 건다:

  ⛔ 반각 영숫자가 섞임          → 바이너리
  ⛔ 작은 가나가 연달아 둘       → 바이너리 (`レぇぉぬ…`)
  ⛔ 글자 2개 이하               → 조각 (`マ反` 류가 수백 건)
  ⛔ 히라가나도 없고 한자도 없음 → 표·ID
  ⛔ 꼬리조각(되짚은 진짜 시작이 다름)

남는 건 **사람이 봐야 하는 목록**이다 — 숫자로 「0건」을 주장하지 않는다.
"""
import os
import re
import struct
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import find_uncovered as FU
from iso9660 import Iso

SKIP = ('.EPK', '.FNT', '.CGB')
SMALL = set('ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ')
ASCII = re.compile(r'[0-9A-Za-z]')
HIRA = re.compile(r'[ぁ-ゖ]')


def main():
    src, dst = sys.argv[1], sys.argv[2]
    corpus = set()
    with open('work/trans/ko.tsv', encoding='utf-8') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 1 and p[0]:
                sh = FU.shape_of_text(p[0])
                if sh:
                    corpus.add(sh)

    a, b = Iso(src), Iso(dst)
    ents = {p.lstrip('/'): (l, s) for p, l, s in a.walk() if not p.endswith('/')}
    import glyphdict
    dic = glyphdict.build('work/uniq')

    # ★한글로 덮인 글리프 칸 — 미번역이 이 칸을 쓰면 화면이 쓰레기가 된다
    #   ([[feedback_font_reuse_untranslated_looks_scrambled]]). 「으모모」가 그것.
    painted = set()
    for name in sorted(ents):
        if not name.upper().endswith('.FNT'):
            continue
        fa = a.read(*ents[name])
        fb = b.read(*ents[name])
        if len(fa) < 18 or len(fa) != len(fb):
            continue
        cnt, tag = struct.unpack_from('>HH', fa, 0)
        if tag != 4 or not 0 < cnt < 4000:
            continue
        for i in range(cnt):
            o = 18 + i * 32
            if fa[o:o + 32] != fb[o:o + 32]:
                painted.add(256 + i)

    groups = defaultdict(list)
    for name in sorted(ents):
        if name.upper().endswith(SKIP):
            continue
        lba, size = ents[name]
        da = a.read(lba, size)
        db = b.read(lba, size)
        if da == db:
            continue
        # 그 모듈이 쓰는 폰트 후보를 전부 합쳐 한자를 푼다(못 풀면 【n】)
        tab = {}
        pre = name.split('.')[0][:4].upper()
        for fn in ents:
            u = fn.upper()
            if not u.endswith('.FNT'):
                continue
            if not (u.startswith(pre) or u[3:7] == pre[-4:]):
                continue
            f = a.read(*ents[fn])
            if len(f) < 18:
                continue
            cnt, tag = struct.unpack_from('>HH', f, 0)
            if tag != 4 or not 0 < cnt < 4000:
                continue
            for i in range(cnt):
                tab.setdefault(256 + i,
                               dic.get(f[18 + i * 32:18 + (i + 1) * 32]))

        for s, e, sh in FU.shapes_in(da):
            if da[s:e] != db[s:e]:
                continue                       # 번역이 들어갔다
            if sh in corpus:
                continue                       # 아는 원문 = find_uncovered 몫
            # 꼬리조각 배제 — 앞쪽 널부터 다시 읽어 끝이 같으면 그게 진짜 시작
            p = da.rfind(b'\x00', max(0, s - 256), s)
            if p >= 0 and p + 1 < s:
                for s2, e2, _ in FU.shapes_in(da[p + 1:s + 2]):
                    if p + 1 + s2 < s:
                        break
                else:
                    pass
            g = [x for x in sh if x != 'c']
            if len(g) <= 2:
                continue
            txt = ''.join('' if x == 'c' else
                          (basemap.ch(x) if isinstance(x, int)
                           else '【?】') for x in sh)
            # 한자는 실제 index 로 다시 푼다
            i2 = s
            real = ''
            while i2 < e:
                bb = da[i2]
                if bb >= 0x80:
                    v = ((bb & 0x7F) << 8) | da[i2 + 1]
                    real += basemap.ch(v) if v < 256 else (tab.get(v) or '【%d】' % v)
                    i2 += 2
                elif bb < 0x20:
                    i2 += 1
                else:
                    real += basemap.ch(bb)
                    i2 += 1
            if ASCII.search(real):
                continue
            prev = False
            bad = False
            for c in real:
                sm = c in SMALL
                if sm and prev:
                    bad = True
                    break
                prev = sm
            if bad:
                continue
            has_kanji = any(x == '*' for x in sh)
            if not HIRA.search(real) and not has_kanji:
                continue
            # 이 문자열이 «덮인 칸»을 쓰나
            danger = []
            i3 = s
            while i3 < e:
                bb = da[i3]
                if bb >= 0x80:
                    v = ((bb & 0x7F) << 8) | da[i3 + 1]
                    if v in painted:
                        danger.append(v)
                    i3 += 2
                else:
                    i3 += 1
            groups[real].append((name, s, sorted(set(danger))))

    print('== 고유 문안 %d개 / 자리 %d곳' % (len(groups), sum(len(v) for v in groups.values())))
    dang = {t: v for t, v in groups.items() if any(p[2] for p in v)}
    print('== 그중 «덮인 칸»을 쓰는 것 = 화면 파손 확정: 고유 %d개 / 자리 %d곳'
          % (len(dang), sum(len(v) for v in dang.values())))
    for t, places in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        p0 = places[0]
        mark = '★파손' if any(p[2] for p in places) else '     '
        print('%s %3d곳  %-14s %06X  %s' % (mark, len(places), p0[0], p0[1], t[:66]))


if __name__ == '__main__':
    main()

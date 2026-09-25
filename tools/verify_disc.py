# -*- coding: utf-8 -*-
"""패치된 디스크를 «되읽어» 번역이 실제로 들어갔는지 확인한다.

  python tools/verify_disc.py <패치된 Track1.bin>

「내 데이터엔 이상 없음」은 검증이 아니다 — 디스크에서 다시 꺼내 비교한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import encode as enc
from iso9660 import Iso


def load(p):
    rows = []
    with open(p, encoding='utf-8') as f:
        f.readline()
        for line in f:
            line = line.rstrip('\n')
            if line:
                rows.append(line.split('\t'))
    return rows


def main():
    dst = sys.argv[1]
    iso = Iso(dst)
    ents = {p.lstrip('/'): (l, s) for p, l, s in iso.walk() if not p.endswith('/')}

    units = load('work/trans/units.tsv')
    id_of = {u[5]: u[0] for u in units}
    ko = {r[0]: r[1] for r in load('work/trans/ko.tsv') if len(r) > 1}
    places = {}
    for p in load('work/trans/places.tsv'):
        places.setdefault(p[0], []).append(p)

    # 빌더와 «같은 방식»으로 기대 바이트를 만든다 — 빌더를 그대로 불러 쓴다.
    import build_kr
    patch = build_kr.build_patch()
    expect = {(f, o): b for f, d in patch.items() for o, b in d.items()}

    cache = {}
    same = diff = miss = skip = 0
    examples = []
    bad = []
    for jp, k in ko.items():
        if k == jp:
            continue
        uid = id_of.get(jp)
        for p in places.get(uid, ()):
            fname = {'MOVIE': 'MOVIE.DAT', 'MENUBK': 'MENUBK.BIN',
                     'COMMON': 'COMMON.DAT'}.get(p[1], p[2] + '.PRG')
            if fname not in ents:
                skip += 1
                continue
            if fname not in cache:
                lba, size = ents[fname]
                cache[fname] = iso.read(lba, size)
            data = cache[fname]
            off = int(p[4], 16)
            budget = int(p[5])
            # ★자리마다 슬롯 크기가 다르다. 인코딩은 «가장 빡빡한» 예산으로
            #   하므로, 디스크에서도 **그 길이만큼만** 잘라 비교해야 한다.
            #   슬롯 크기로 자르면 뒤에 남은 원본 바이트까지 딸려와 전부 불일치가 난다.
            raw = data[off:off + budget]
            # ★정확 대조 — 빌더가 쓴 것과 «똑같은» 바이트가 디스크에 있어야 한다.
            want = expect.get((fname, off))
            if want is None:
                skip += 1
                continue
            raw = raw[:len(want)]
            if raw == want:
                same += 1
                if len(examples) < 4:
                    examples.append((fname, p[4], jp[:20], k[:20],
                                     raw[:10].hex()))
            else:
                diff += 1
                if len(bad) < 6:
                    bad.append((fname, p[4], jp[:20], k[:20],
                                raw[:10].hex(), want[:10].hex()))

    print('되읽기 정확 대조: 일치 %d곳 / **불일치 %d곳** / 대상 아님 %d곳'
          % (same, diff, skip))
    for e in examples:
        print('   OK %-14s %s  %s → %s  [%s]' % e)
    for e in bad:
        print('   ★불일치 %-12s %s  %s → %s  디스크[%s] 기대[%s]' % e)

    # 폰트가 실제로 바뀌었나 — 원본과 대조
    src = sys.argv[2] if len(sys.argv) > 2 else None
    if src and os.path.exists(src):
        iso2 = Iso(src)
        e2 = {p.lstrip('/'): (l, s) for p, l, s in iso2.walk()
              if not p.endswith('/')}
        for fn in ('COMMON.DAT', 'TWN_ZOAH.PRG', 'MOVIE.DAT', 'MENUBK.BIN'):
            if fn not in ents or fn not in e2:
                continue
            a = iso.read(*ents[fn])
            b = iso2.read(*e2[fn])
            nd = sum(1 for x, y in zip(a, b) if x != y)
            print('   %-14s 원본과 다른 바이트 %d / %d' % (fn, nd, len(a)))


if __name__ == '__main__':
    main()

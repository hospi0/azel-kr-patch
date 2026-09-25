# -*- coding: utf-8 -*-
"""안 덮인 자리 — «모듈 폰트로 디코드해 원문과 직접 대조».

  python tools/find_uncovered2.py <무수정원본Track1> <빌드본Track1> [--tsv 출력]

★`find_uncovered.py`(골격 대조)는 **짧은 문자열을 원리상 못 본다** —
  「와일드카드 0개면 3글자 이상 / 한자가 섞이면 5글자 이상」 이라는 문턱 때문에
  `酸` 같은 **한 글자짜리**가 통째로 빠진다. 실기에서 적의 산성 공격 이름판이
  일본어로 남아 있는 걸로 드러났다.

여기서는 문턱 대신 **정확 일치**를 쓴다.
  ① `places.tsv` 의 «모듈 → FNT» 대응으로 그 모듈의 글리프표를 만든다.
  ② 원본의 널종단 토큰열을 그 표로 **글자로 디코드**한다.
  ③ 그 글자열이 `units.tsv` 의 원문과 **똑같고** 빌드본에서 바이트가 안 바뀌었으면
     = 안 덮인 자리.
문턱이 없으므로 1글자도 잡힌다. 대신 «그 모듈의 폰트»를 맞게 골라야 한다
([[feedback_per_region_font_not_per_file]]).
"""
import os
import struct
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import basemap
from iso9660 import Iso

SKIP = ('.EPK', '.FNT', '.CGB')


def main():
    src, dst = sys.argv[1], sys.argv[2]
    out_tsv = sys.argv[sys.argv.index('--tsv') + 1] if '--tsv' in sys.argv else None

    import glyphdict
    dic = glyphdict.build('work/uniq')

    # 모듈 → FNT, 그리고 이미 덮은 자리
    mod_fnt = defaultdict(set)
    covered = defaultdict(set)
    for line in open('work/trans/places.tsv', encoding='utf-8').read().split('\n')[1:]:
        p = line.split('\t')
        if len(p) < 7:
            continue
        fn = {'MOVIE': 'MOVIE.DAT', 'MENUBK': 'MENUBK.BIN',
              'COMMON': 'COMMON.DAT'}.get(p[1], p[2] + '.PRG')
        mod_fnt[fn].add(p[3])
        covered[fn].add(int(p[4], 16))

    jpset = set()
    for line in open('work/trans/units.tsv', encoding='utf-8').read().split('\n')[1:]:
        p = line.split('\t')
        if len(p) >= 6 and p[5]:
            jpset.add(p[5])
    ko = {}
    for line in open('work/trans/ko.tsv', encoding='utf-8'):
        p = line.rstrip('\n').split('\t')
        if len(p) >= 2 and p[1]:
            ko[p[0]] = p[1]

    a, b = Iso(src), Iso(dst)
    ents = {p.lstrip('/'): (l, s) for p, l, s in a.walk() if not p.endswith('/')}
    rows = []
    for name in sorted(mod_fnt):
        if name not in ents or name.upper().endswith(SKIP):
            continue
        da = a.read(*ents[name])
        db = b.read(*ents[name])
        # 그 모듈이 쓰는 FNT 를 합쳐 글리프표를 만든다
        tab = {}
        for fn in mod_fnt[name]:
            p = fn + '.FNT'
            if p not in ents:
                continue
            f = a.read(*ents[p])
            if len(f) < 18:
                continue
            cnt, tag = struct.unpack_from('>HH', f, 0)
            if tag != 4 or not 0 < cnt < 4000:
                continue
            for i in range(cnt):
                tab.setdefault(256 + i, dic.get(f[18 + i * 32:18 + (i + 1) * 32]))
        i = 0
        n = len(da)
        while i < n - 1:
            if da[i] < 0x80:
                i += 1
                continue
            s = i
            txt = []
            ok = True
            while i < n and da[i] != 0:
                c = da[i]
                if c >= 0x80:
                    if i + 1 >= n:
                        ok = False
                        break
                    v = ((c & 0x7F) << 8) | da[i + 1]
                    ch = basemap.ch(v) if v < 256 else tab.get(v)
                    if ch is None:
                        ok = False
                        break
                    txt.append(ch)
                    i += 2
                elif c < 0x20:
                    txt.append('<%02X>' % c)
                    i += 1
                else:
                    txt.append(basemap.ch(c))
                    i += 1
            e = i
            i += 1
            if not ok or not txt:
                continue
            t = ''.join(txt)
            if t not in jpset or s in covered[name]:
                continue
            if da[s:e] != db[s:e]:
                continue                       # 이미 뭔가 들어갔다
            rows.append((name, s, e - s, t, ko.get(t, '')))
    print('== 안 덮인 자리 %d곳 / 고유 원문 %d개'
          % (len(rows), len({r[3] for r in rows})))
    for name, s, ln, t, k in rows[:60]:
        print('   %-14s %06X %3d  %s → %s' % (name, s, ln, t[:30], k[:30]))
    if out_tsv:
        with open(out_tsv, 'w', encoding='utf-8', newline='\n') as f:
            f.write('file\toffset\tlen\tjp\tko\n')
            for name, s, ln, t, k in rows:
                f.write('%s\t%06X\t%d\t%s\t%s\n' % (name, s, ln, t, k))
        print('→ %s' % out_tsv)


if __name__ == '__main__':
    main()

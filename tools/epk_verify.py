# -*- coding: utf-8 -*-
"""구운 디스크에서 EPK 자막을 **되읽어** 번역표와 정확 대조한다.

  python tools/epk_verify.py <디스크번호> <패치본Track1> <무수정원본Track1>

되읽기는 «패치본 자체의 폰트»로 한다 — 빌더가 쓴 index→글자 배정을
빌더와 같은 규칙으로 다시 만들어 대조하므로, 빌더가 잘못 쓴 자리는
그대로 드러난다. 원문이 남아 있어야 할 미번역 자막도 함께 확인한다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import epk_scan2
import epk_build2
import krglyph
from iso9660 import Iso

FONT_DATA = 0x28 + 4 + 14
TOK = re.compile(r'<!([0-9A-F]{2})>|<([0-9A-F]{2})>|\\n|(.)', re.S)


def base_map():
    m = dict(basemap.REVERSE_KEEP)
    with open('work/charmap.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) == 3 and p[0] == 'base':
                m[p[1]] = int(p[2])
    return m


def main():
    disc, dst, src = sys.argv[1], sys.argv[2], sys.argv[3]
    base = base_map()
    rbase = {v: k for k, v in base.items()}
    ko = {}
    with open('work/epk_ko.tsv', encoding='utf-8') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 4 and p[0] == disc and p[3]:
                ko[(p[1], int(p[2], 16))] = p[3]

    iso_s, iso_d = Iso(src), Iso(dst)
    ents = {p.lstrip('/'): (l, s) for p, l, s in iso_s.walk() if not p.endswith('/')}
    font = krglyph.load('Galmuri11')
    ok = miss = bad = intact = broke = 0
    for name in sorted(n for n in ents if n.upper().endswith('.EPK')):
        lba, size = ents[name]
        so = iso_s.read(lba, size)
        do = iso_d.read(lba, size)
        n = epk_scan2.nfont_of(so)
        res = epk_scan2.scan(so, n)
        # ★2026-08-15: 빌더가 합치는 «추가 자막 목록»을 검증기도 똑같이 합쳐야 한다.
        #   안 그러면 장면 폰트 배정이 어긋나 **거짓 불일치**가 쏟아진다
        #   (실측: D3 에서 불일치 45·글리프누락 70 이 전부 이 탓이었다).
        for eo, eln, eidx in epk_build2.EXTRA.get((str(disc), name), ()):
            if all(eo != o for o, _, _ in res):
                res.append((eo, eln, eidx))
        res.sort()
        # 빌더와 같은 규칙으로 장면 폰트 배정을 되만든다
        reserved = set()
        todo = []
        for o, ln, idx in res:
            k = ko.get((name, o))
            if k:
                todo.append((o, ln, k))
            else:
                reserved |= {v - 256 for v in idx if v >= 256}
        free = [i for i in range(n) if i not in reserved]
        need = []
        for _, _, k in todo:
            for m in TOK.finditer(k):
                c = m.group(3)
                if c and c not in base and c not in need:
                    need.append(c)
        scene = {256 + free[i]: c for i, c in enumerate(need) if i < len(free)}

        for o, ln, idx in res:
            k = ko.get((name, o))
            raw = do[o:o + ln]
            if k is None:
                # 미번역 = 바이트가 그대로여야 하고, 쓰는 폰트 칸도 안 바뀌어야 한다
                if raw != so[o:o + ln]:
                    print('★미번역이 바뀌었다 %s %06X' % (name, o))
                    broke += 1
                else:
                    keep = True
                    for v in idx:
                        if v >= 256:
                            g = FONT_DATA + (v - 256) * 32
                            if do[g:g + 32] != so[g:g + 32]:
                                keep = False
                    if keep:
                        intact += 1
                    else:
                        print('★미번역이 쓰는 폰트 칸이 덮였다 %s %06X' % (name, o))
                        broke += 1
                continue
            # 번역 = 되읽어 문자열 비교
            i, got = 0, []
            while i < ln:
                b = raw[i]
                if b == 0:
                    break
                if b >= 0x80:
                    v = ((b & 0x7F) << 8) | raw[i + 1]
                    i += 2
                    # ★index 1 은 «공백»이자 패딩이다 — 여기서 지우면 진짜
                    #   공백까지 사라진다. 꼬리 패딩은 마지막에 rstrip 한다.
                    got.append(scene.get(v) or rbase.get(v) or basemap.ch(v))
                elif b < 0x20:
                    got.append('<%02X>' % b)
                    i += 1
                else:
                    got.append(basemap.ch(b))
                    i += 1
            g = ''.join(got)
            g = re.sub(r'^(?:<[0-9A-F]{2}>)+', '', g).rstrip()   # 선두 제어·꼬리 패딩
            want = ''.join(m.group(3) or ('\\n' if m.group(0) == '\\n' else '')
                           for m in TOK.finditer(k))
            if g.replace('<06>', '\\n') == want:
                ok += 1
            else:
                bad += 1
                print('★불일치 %s %06X\n   기대 %s\n   실제 %s' % (name, o, want, g))
        # 폰트 칸이 실제로 그 글자로 구워졌는지
        for v, c in scene.items():
            g = FONT_DATA + (v - 256) * 32
            if do[g:g + 32] != krglyph.glyph(font, c):
                print('★글리프 안 구워짐 %s idx%d %s' % (name, v - 256, c))
                miss += 1
    print('D%s 되읽기 — 일치 %d / 불일치 %d / 글리프누락 %d / 미번역보존 %d / 미번역파손 %d'
          % (disc, ok, bad, miss, intact, broke))


if __name__ == '__main__':
    main()

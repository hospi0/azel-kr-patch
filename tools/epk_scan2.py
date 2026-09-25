# -*- coding: utf-8 -*-
"""`.EPK` 자막 검출 — 정밀·고속판.

  python tools/epk_scan2.py <Track1.bin> [태그] > work/epk_<태그>.tsv

★**폰트 칸을 덮어쓰려면 그 폰트를 쓰는 문자열을 하나도 빠짐없이** 잡아야 한다.
  하나만 놓치면 그 칸을 못 쓴다(실기에 「왜카?」가 나온 원인).

판정 세 가지를 **바이트 수준에서 먼저** 걸어 잡음을 쳐낸다(그래야 빠르다).
  ① 2바이트 토큰이 이어지다 널로 끝난다
  ② 모든 index 가 «기본폰트 0~255 + 자체 폰트» 안에 든다
     — 이 범위를 벗어나면 글자가 아니라 바이너리다
  ③ 자체 폰트 index 를 쓰면 무조건 자막(통계 문턱 없이 채택),
     안 쓰면 가나 비율로 거른다
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import strtab

KANA = {i for i in range(256) if '぀' <= basemap.ch(i) <= 'ヿ'}
PUNCT = {i for i in range(256) if basemap.ch(i) in '、。「」『』！？…（）・ー'}


def nfont_of(data):
    n, tag = struct.unpack_from('>HH', data, 0x28)
    return n if tag == 0x0004 and 0 < n < 4000 else 0


def glyphs_of(data, n):
    s = 0x28 + 4 + 14
    return [data[s + i * 32: s + (i + 1) * 32] for i in range(n)]


def scan(data, nfont):
    """[(offset, 길이, index열)] — 자막."""
    hi = 256 + nfont
    lead_ok = bytes(range(0x80, 0x80 + (hi >> 8) + 1))
    pat = re.compile(b'(?:[' + re.escape(lead_ok) + b'].){2,}\\x00')
    # ★폰트 비트맵은 문자열이 아니다 — 16행 BE16 이라 `80 xx` 로 보이는 줄이
    #   흔해 오탐이 난다(D3 E078 0x9C). 헤더+글리프 구간은 아예 건너뛴다.
    font_end = 0x28 + 4 + 14 + 32 * nfont
    out = []
    seen = set()
    for m in pat.finditer(data):
        s, e = m.start(), m.end()
        if s < font_end:
            continue
        idx = []
        ok = True
        i = s
        while i < e - 1:
            b = data[i]
            if b < 0x80:
                ok = False
                break
            v = ((b & 0x7F) << 8) | data[i + 1]
            if v >= hi:
                ok = False
                break
            idx.append(v)
            i += 2
        if not ok or i != e - 1 or len(idx) < 2:
            continue
        # ★★진짜 시작점으로 되짚는다.
        #   문자열이 «제어코드»나 «1바이트 토큰»으로 시작하면 위 정규식이 그
        #   자리를 못 잡고 **중간부터** 읽는다. 그 상태로 폰트 칸을 덮으면
        #   앞부분이 쓰레기가 된다(실기: 「待てよ、人違いだって」가
        #   「탑린、탑린젤장못사람 잘못 봤다고」로 나왔다).
        #   앞쪽 널 다음부터 다시 읽어 **끝이 같은 곳으로 떨어지면** 그게 진짜 시작.
        p = data.rfind(b'\x00', max(0, s - 96), s)
        if p >= 0 and p + 1 < s:
            t, _ = strtab.parse_table(data, p + 1, hi, lenient=False)
            if t:
                o2, raw2, tk2 = t[0]
                if o2 + len(raw2) + 1 == e:
                    g2 = [v for k, v in tk2 if k in ('g', 'g1')]
                    if g2 and all(v < hi for v in g2):
                        s = o2
                        idx = g2
        if s in seen:
            continue
        own = [v for v in idx if v >= 256]
        if not own:
            base = [v for v in idx if v < 256]
            kana = sum(1 for v in base if v in KANA or v in PUNCT)
            if len(idx) < 4 or kana < 3 or kana < len(base) * 0.6:
                continue
            if strtab.is_asset_name(data[s:e - 1]):
                continue
        seen.add(s)
        out.append((s, e - s, idx))
    return out


def main():
    from iso9660 import Iso
    import glyphdict
    iso = Iso(sys.argv[1])
    dic = glyphdict.build('work/uniq')
    print('name\toffset\tlen\ttext', flush=True)
    for name, lba, size in iso.walk():
        if not name.upper().endswith('.EPK'):
            continue
        data = iso.read(lba, size)
        n = nfont_of(data)
        tab = [dic.get(g) for g in glyphs_of(data, n)]
        res = scan(data, n)
        used = sorted({v - 256 for _, _, idx in res for v in idx if v >= 256})
        print('# %-12s 폰트 %3d / 자막 %3d개 / 쓰는 칸 %s'
              % (name, n, len(res),
                 ('0~%d(%d개)' % (max(used), len(used))) if used else '없음'),
              file=sys.stderr, flush=True)
        for o, ln, idx in res:
            txt = ''.join(basemap.ch(v) if v < 256
                          else (tab[v - 256] or '【%d】' % (v - 256))
                          for v in idx)
            print('%s\t%06X\t%d\t%s' % (name.strip('/'), o, ln, txt), flush=True)


if __name__ == '__main__':
    main()

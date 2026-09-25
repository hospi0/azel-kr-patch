# -*- coding: utf-8 -*-
"""`.EPK`(컷신 패키지) 안의 자막을 찾는다.

  python tools/scan_epk.py <Track1.bin>

★`.EPK` 는 지금까지 한 번도 스캔하지 않은 텍스트 소스다 —
  `MOVIE.DAT` → `MENUBK.BIN` → `COMMON.DAT` 에 이은 **네 번째**.
  실기 스샷(「何が起こってるんだ…」)으로만 드러났다.

바이트마다 파서를 돌리면 34MB 에서 15분이 지나도 안 끝난다.
**정규식으로 «2바이트 글리프 토큰이 여러 개 이어지다 널로 끝나는 곳»만 추린 뒤**
그 자리만 파싱한다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import strtab

# 2바이트 토큰 2개 이상 + 널. 리드바이트는 0x80~0x8F 면 충분하다(index < 4096).
# ★4개 이상으로 잡았다가 `何だ？`(3글자) 를 놓쳤다. 그 자막을 못 잡은 채
#   그 EPK 폰트 칸을 한글로 덮어써서, 실기에 「왜다?」 같은 쓰레기가 나왔다.
RUN = re.compile(rb'(?:[\x80-\x8f].){2,}\x00')

KANA = {i for i in range(256) if '぀' <= basemap.ch(i) <= 'ヿ'}
PUNCT = {i for i in range(256) if basemap.ch(i) in '、。「」『』！？…（）・ー'}


def nfont_of(data):
    """EPK 머리 0x28 의 자체 폰트 글리프 수."""
    import struct
    n, tag = struct.unpack_from('>HH', data, 0x28)
    return n if tag == 0x0004 and 0 < n < 4000 else 0


def scan(data, nfont=0):
    """nfont = 그 EPK 자체 폰트의 글리프 수.

    ★**자체 폰트 index(256..256+nfont)를 쓰는 문자열은 무조건 자막이다** —
      그 폰트는 자막 말고 쓸 데가 없다. 이게 통계 문턱보다 훨씬 강한 기준이고,
      **폰트 칸을 덮어써도 되는지 판단하려면 이걸 빠짐없이 잡아야 한다**.
      가나 비율 문턱만 쓰다가 `何だ？` 를 놓쳐 실기에 쓰레기가 나왔다.
    """
    out = []
    seen = set()
    for m in RUN.finditer(data):
        s = m.start()
        tab, _ = strtab.parse_table(data, s, 0x8000, lenient=False)
        if not tab:
            continue
        o, raw, t = tab[0]
        if not raw or o in seen:
            continue
        g = [v for k, v in t if k in ('g', 'g1')]
        # ★자막이 쓸 수 있는 index 는 «기본폰트 0~255 + 자체 폰트» 뿐이다.
        #   그 범위를 벗어난 index 가 하나라도 있으면 글자가 아니라 바이너리다.
        #   (이 제약 없이 시작 후보를 넓혔더니 index 2304 짜리 잡음이 쏟아졌다)
        if nfont and any(v >= 256 + nfont for v in g):
            continue
        own = [v for v in g if 256 <= v < 256 + nfont]
        if not own:                        # 자체 폰트를 안 쓰면 통계로 거른다
            if len(g) < 4:
                continue
            base = [v for v in g if v < 256]
            kana = sum(1 for v in base if v in KANA or v in PUNCT)
            if not base or kana < len(base) * 0.6 or kana < 3:
                continue
        elif len(g) < 2:
            continue
        seen.add(o)
        txt = ''.join(basemap.ch(v) if v < 256 else '【%d】' % (v - 256)
                      for v in g)
        out.append((o, len(raw) + 1, txt))
    return out


def main():
    sys.path.insert(0, os.path.dirname(__file__))
    from iso9660 import Iso
    iso = Iso(sys.argv[1])
    eps = [(n, l, s) for n, l, s in iso.walk() if n.upper().endswith('.EPK')]
    tot = totc = 0
    print('name\toffset\tlen\ttext')
    for name, lba, size in eps:
        data = iso.read(lba, size)
        res = scan(data, nfont_of(data))
        tot += len(res)
        totc += sum(len(x[2]) for x in res)
        print('# %-12s %9d B → 자막 후보 %4d개 / %6d자'
              % (name, size, len(res), sum(len(x[2]) for x in res)),
              file=sys.stderr)
        for o, ln, txt in res:
            print('%s\t%06X\t%d\t%s' % (name.strip('/'), o, ln, txt))
    print('# 합계 %d개 / %d자' % (tot, totc), file=sys.stderr)


if __name__ == '__main__':
    main()

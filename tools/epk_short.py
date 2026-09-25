# -*- coding: utf-8 -*-
"""EPK 에서 «짧은 자막»을 찾는다 — `epk_scan2` 가 원리상 놓치는 것들.

`epk_scan2.scan()` 은 자체 폰트(index>=256)를 안 쓰는 문자열에 대해
`len(idx) < 4 or kana < 3` 이면 버린다. 그래서 「えっ？」(3글자) 같은 짧은 자막이
통째로 빠지고, **그 자막이 쓰는 기본폰트 칸이 한글로 갈려** 실기에 쓰레기가 뜬다
(실기 2026-08-15: E021 에서 「えっ？」가 「더최?」로 나왔다).

판정 = ①앞뒤가 NUL ②토큰이 2~3개 ③전부 가나·문장부호 ④2바이트 토큰만
       ⑤이미 검출된 자막과 겹치지 않음.
⛔EPK 는 대부분 영상 데이터라 조건을 느슨하게 하면 오탐이 쏟아진다.

사용: python epk_short.py <디스크Track1> [디스크번호]
"""
import sys, os, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from iso9660 import Iso
import basemap
import epk_scan2 as S

T = basemap.TABLE
OK = set(S.KANA) | set(S.PUNCT)


def find(data, nfont, known):
    font_end = 0x28 + 4 + 14 + 32 * nfont
    out = []
    i = font_end
    n = len(data)
    while i < n - 6:
        if data[i] != 0:
            i += 1
            continue
        j = i + 1
        # 선두 1바이트 토큰(공백 등) 허용
        head = 0
        if j < n and 0x01 <= data[j] < 0x20:
            head = 1
            j += 1
        toks = []
        while j + 1 < n and 0x80 <= data[j] <= 0x80 + (255 >> 8) + 1:
            v = ((data[j] & 0x7F) << 8) | data[j + 1]
            if v >= 256:
                toks = []
                break
            toks.append(v)
            j += 2
        if 2 <= len(toks) <= 3 and j < n and data[j] == 0:
            # ★이미 검출된 자막 «안쪽»에서 시작하는 조각은 버린다.
            #   시작 오프셋만 비교하면 꼬리 조각이 전부 새 자막으로 잡힌다
            #   (실측: 그렇게 하면 D2·D3 에서 17건 중 대부분이 오탐이었다).
            inside = any(a < i + 1 < a + b for a, b in known)
            if all(v in OK for v in toks) and not inside:
                s = ''.join(T[v] if v < len(T) and T[v] else '?' for v in toks)
                out.append((i + 1, j - i - 1 + 1, ('　' if head else '') + s))
        i += 1
    return out


def main():
    iso = Iso(sys.argv[1])
    m = {p.split('/')[-1]: (l, s) for p, l, s in iso.walk()}
    known = {}
    for name in sorted(k for k in m if k.endswith('.EPK')):
        data = iso.read(*m[name])
        nfont = struct.unpack_from('>H', data, 0x28)[0]
        ks = [(o, ln) for o, ln, _ in S.scan(data, nfont)]
        res = find(data, nfont, ks)
        print('%-12s 폰트 %3d / 검출된 자막 %3d / ★놓친 짧은 자막 %d개'
              % (name, nfont, len(ks), len(res)))
        for o, ln, s in res:
            print('    0x%06X  %2dB  %r' % (o, ln, s))


if __name__ == '__main__':
    main()

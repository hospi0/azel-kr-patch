# -*- coding: utf-8 -*-
"""스테이트 두 장을 비교해 «그 화면이 새로 쓴 메모리»를 찾는다 — 워치포인트 대용.

  python tools/diff_state.py work/before.bin work/after.bin

메뉴를 열기 «직전»과 «연 뒤» 스냅샷을 비교하면, 메뉴가 채운 버퍼가 드러난다.
디버거를 못 쓰는 환경에서 «어디서 읽어오나»를 좁히는 가장 싼 방법이다.
"""
import sys


def main():
    a = open(sys.argv[1], 'rb').read()
    b = open(sys.argv[2], 'rb').read()
    n = min(len(a), len(b))
    print('스냅샷 %d B — 다른 바이트 세는 중' % n)

    runs = []
    i = 0
    while i < n:
        if a[i] != b[i]:
            s = i
            gap = 0
            while i < n and gap < 32:
                if a[i] != b[i]:
                    gap = 0
                else:
                    gap += 1
                i += 1
            runs.append((s, i - gap))
        i += 1

    runs.sort(key=lambda r: -(r[1] - r[0]))
    tot = sum(r[1] - r[0] for r in runs)
    print('바뀐 구간 %d개 / 합계 %d B' % (len(runs), tot))
    print('\n큰 구간 25개:')
    for s, e in runs[:25]:
        print('   %08X..%08X  %6d B' % (s, e, e - s))


if __name__ == '__main__':
    main()

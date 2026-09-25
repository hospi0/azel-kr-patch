# -*- coding: utf-8 -*-
"""검출기가 «진짜 시작점»을 찾은 뒤, 번역표를 새 오프셋으로 옮긴다.

  python tools/epk_remap.py > work/epk_ko_new.tsv

되짚기를 넣자 문자열 시작이 1~17바이트 앞으로 정정됐다. 옛 번역표는 옛
오프셋을 키로 쓰므로 그대로 두면 **문자열 한가운데에 쓴다**(실기에서
「탑린、탑린젤장못…」이 그렇게 나왔다).

옮기는 규칙 = 옛 오프셋이 새 문자열의 **바이트 범위 안**에 들면 그 번역을 잇는다.
원문이 길어진 것(앞부분이 새로 붙은 것)은 번역을 다시 해야 하므로 표시한다.
"""
import sys


def main():
    old = {}
    with open('work/epk_ko.tsv', encoding='utf-8') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 4 and p[3]:
                old[(p[0], p[1], int(p[2], 16))] = p[3]

    units = []
    with open('work/epk_units.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 7:
                units.append(p)

    n = miss = grew = 0
    for p in units:
        disc, epk, off, ln, mx, frag, jp = p[0], p[1], int(p[2], 16), int(p[3]), \
            int(p[4]), p[5], p[6]
        hit = [(o, v) for (d, e, o), v in old.items()
               if d == disc and e == epk and off <= o < off + ln]
        if not hit:
            miss += 1
            print('# 미대응\t%s\t%s\t%06X\t%d칸\t%s' % (disc, epk, off, mx, jp),
                  file=sys.stderr)
            continue
        hit.sort()
        ko = hit[0][1]
        if hit[0][0] != off:
            grew += 1
            print('# 시작이 %d바이트 앞으로\t%s\t%s\t%06X\t%s\t→ %s'
                  % (hit[0][0] - off, disc, epk, off, jp, ko), file=sys.stderr)
        n += 1
        print('%s\t%s\t%06X\t%s' % (disc, epk, off, ko))
    print('# 옮김 %d / 미대응 %d / 시작 정정 %d' % (n, miss, grew), file=sys.stderr)


if __name__ == '__main__':
    main()

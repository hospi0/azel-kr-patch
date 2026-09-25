# -*- coding: utf-8 -*-
"""쓰기 구간이 서로 겹치는지 본다.

같은 파일 안에서 두 항목의 [오프셋, 오프셋+길이) 가 겹치면 나중에 쓰는 쪽이
앞의 것을 덮는다. 원문 길이를 지켜도 **패딩 공백**이 이웃을 침범할 수 있다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import build_kr


def main():
    patch = build_kr.build_patch()
    total = 0
    for fname, edits in sorted(patch.items()):
        items = sorted((o, len(b)) for o, b in edits.items())
        for (o1, l1), (o2, l2) in zip(items, items[1:]):
            if o1 + l1 > o2:
                total += 1
                if total <= 20:
                    print('  %-14s %06X(+%d) 가 %06X 를 %d바이트 침범'
                          % (fname, o1, l1, o2, o1 + l1 - o2))
    print('\n겹치는 쓰기 %d곳' % total)


if __name__ == '__main__':
    main()

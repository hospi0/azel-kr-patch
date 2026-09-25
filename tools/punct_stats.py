# -*- coding: utf-8 -*-
"""번역문의 문장부호 뒤 공백 실태.

  python tools/punct_stats.py

★전각 고정폭이라 공백 하나가 **한 칸을 통째로 먹는다**
  ([[feedback_no_space_after_punct]]). 쉼표·마침표 뒤는 무조건 삭제가 규칙이고,
  물음표·느낌표는 갈리므로 **어느 쪽이 다수인지 세어 보고** 통일한다.
"""
import re

SKIP = set('?!.,') | {'\\'}


def main():
    with_sp = no_sp = 0
    for line in open('work/trans/ko.tsv', encoding='utf-8'):
        c = line.rstrip('\n').split('\t')
        if len(c) < 2 or not c[1]:
            continue
        ko = c[1]
        for m in re.finditer(r'[?!]', ko):
            j = m.end()
            if j >= len(ko):
                continue
            if ko[j] == ' ':
                with_sp += 1
            elif ko[j] in SKIP:
                continue
            else:
                no_sp += 1
    print('물음표·느낌표 뒤 — 공백 있음 %d / 없음 %d' % (with_sp, no_sp))


if __name__ == '__main__':
    main()

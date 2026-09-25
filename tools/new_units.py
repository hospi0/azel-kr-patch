# -*- coding: utf-8 -*-
"""검출기 수정으로 «새로 들어온» 번역 대상만 뽑는다.

  python tools/new_units.py > work/trans/new_units.tsv

기존 번역표(`work/trans/ko.tsv`)에 원문 키가 없는 것 = 이번에 새로 잡힌 것.
쓰레기(미해독 토큰 `<!XX>` 가 섞인 것, 글자 수가 너무 적은 것)는 뺀다 —
검출기가 구간을 잡을 때 사이에 낀 바이너리까지 함께 들어오기 때문이다.
"""
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import textmodel2

KANA = {i for i in range(256) if '぀' <= basemap.ch(i) <= 'ヿ'}
BAD = re.compile(r'<!')


def is_clean(it):
    """사람이 읽을 수 있는 «진짜 텍스트» 인가."""
    txt = it['text']
    if BAD.search(txt):
        return False
    g = [v for k, v in it['toks'] if k in ('g', 'g1')]
    if len(g) < 3:
        return False
    # ★제어코드가 글자 사이사이에 박혀 있으면 대사가 아니라 스크립트 바이트다
    #   (「ゆ)？<08>セ<0E>れ<0C>ら…」). 진짜 대사의 제어코드는 개행 정도다.
    ctrl = sum(1 for k, _ in it['toks'] if k == 'c')
    if ctrl > len(it['toks']) * 0.2:
        return False
    if len(set(g)) < 2:            # 「ななななな…」 같은 채움값
        return False
    base = [v for v in g if v < 256]
    scene = [v for v in g if v >= 256]
    # 장면 FNT 한자가 섞여 있으면 대사가 거의 확실하다.
    if scene:
        return True
    kana = sum(1 for v in base if v in KANA)
    return kana >= len(base) * 0.7 and kana >= 3


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else 'work/uniq'
    old = set()
    with open('work/trans/ko.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if p:
                old.add(p[0])

    items = textmodel2.collect(d)
    new = {}
    for it in items:
        if it['kind'] == 'asset' or it['text'] in old:
            continue
        if not is_clean(it):
            continue
        e = new.setdefault(it['text'], dict(kind=it['kind'], budget=it['budget'],
                                            mods=set(), n=0))
        e['mods'].add(it['module'])
        e['budget'] = min(e['budget'], it['budget'])
        e['n'] += 1

    print('jp\tkind\tbudget\tcount\tmodules')
    for t, e in sorted(new.items(), key=lambda kv: -kv[1]['n']):
        print('%s\t%s\t%d\t%d\t%s'
              % (t, e['kind'], e['budget'], e['n'], ','.join(sorted(e['mods']))))
    c = Counter(e['kind'] for e in new.values())
    print('# 새 번역 단위 %d개 / %d자  %s'
          % (len(new), sum(len(t) for t in new), dict(c)), file=sys.stderr)


if __name__ == '__main__':
    main()

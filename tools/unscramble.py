# -*- coding: utf-8 -*-
"""실기에서 깨져 보이는 글자 → 원래 무슨 글자였나 되짚는다.

  python tools/unscramble.py 것를크 [다른것 ...]

★반드시 **그 디스크를 구운 배정표**(`work/charmap.tsv`)로 풀어야 한다.
  번역문이 조금만 바뀌어도 «글자→index» 가 통째로 달라지므로, 나중 배정으로
  풀면 아무것도 안 맞는다(실제로 그렇게 헛다리를 짚었다).

화면에 보이는 한글을 index 로 되돌리고, 그 index 를 **원본 폰트**로 읽는다.
어느 폰트가 물렸는지는 «결과가 일본어로 말이 되는가»로 가린다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import fntmap

MAP = 'work/charmap.tsv'


def load_charmap():
    base, scene = {}, {}
    with open(MAP, encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) != 3:
                continue
            scope, ch, idx = p[0], p[1], int(p[2])
            if scope == 'base':
                base[ch] = idx
            else:
                scene.setdefault(scope, {})[ch] = idx
    return base, scene


def main():
    if not os.path.exists(MAP):
        raise SystemExit('배정표가 없다: %s (빌드를 한 번 돌리면 생긴다)' % MAP)
    base, scene = load_charmap()
    rev_keep = basemap.REVERSE_KEEP

    for word in sys.argv[1:]:
        print('\n=== %r' % word)
        idx = []
        for ch in word:
            if ch in base:
                idx.append(('base', base[ch]))
            elif ch in rev_keep:
                idx.append(('keep', rev_keep[ch]))
            else:
                idx.append(('?', None))
        print('   index =', [i for _, i in idx])
        if any(i is None for _, i in idx):
            print('   ★배정표에 없는 글자가 있다 — 장면 FNT 쪽일 수 있다')
        # 기본 폰트로 읽기
        if all(i is not None for _, i in idx):
            print('   기본폰트: %s'
                  % ''.join(basemap.ch(i) for _, i in idx))
        # 장면 FNT 로도 (그 폰트에 배정된 글자면 그 index 를 쓴다)
        for fn, m in sorted(scene.items()):
            try:
                sc = fntmap.load(fn)
            except Exception:
                continue
            out = []
            ok = True
            for ch in word:
                if ch in m:
                    i = m[ch] - 256
                    out.append(sc[i] if i < len(sc) else '?')
                elif ch in base:
                    out.append(basemap.ch(base[ch]))
                elif ch in rev_keep:
                    out.append(ch)
                else:
                    ok = False
                    break
            if ok and any(c in m for c in word):
                print('   %-10s %s' % (fn, ''.join(out)))


if __name__ == '__main__':
    main()

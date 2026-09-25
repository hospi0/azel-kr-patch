# -*- coding: utf-8 -*-
"""글자 하나짜리 «문자열» 을 원문으로 되돌린다 — 이건 텍스트가 아니다.

증거
  · `FLAGEDIT` 에 な(32) に(33) ぬ(34) ね(35) 가 나란히 있다 — 글리프 인덱스가
    **완벽한 연속**이다. 글자로 읽으면 뜻이 없고 숫자로 읽으면 카운터다.
  · 다른 모듈의 `)`(60)·`…`(58)·`？`(64) 도 지도 이름 앞에 붙는 마커다
    (`)<1D><1A><01>キャラバン` 꼴). 홀로 나오면 마커 바이트만 있는 것.

이걸 「よ→요」처럼 번역하면 **그 1바이트 값이 바뀐다**. 게다가 예산이 2바이트뿐
이라 한글을 넣으려면 1바이트 칸을 억지로 잡아먹어 정작 필요한 곳이 밀린다.
"""
import pickle
import sys

CACHE = 'work/toks.pkl'


def load(p):
    rows = []
    with open(p, encoding='utf-8') as f:
        head = f.readline()
        for line in f:
            line = line.rstrip('\n')
            if line:
                rows.append(line.split('\t'))
    return rows


def main():
    model = pickle.load(open(CACHE, 'rb'))
    single = set()
    for text, (toks, budget, kind) in model.items():
        g = [v for k, v in toks if k in ('g', 'g1')]
        if len(toks) == 1 and len(g) == 1 and g[0] < 256:
            single.add(text)
    print('글자 하나짜리 단위 %d개' % len(single))

    import os
    krdir = 'work/trans/kr'
    n = 0
    for fn in sorted(os.listdir(krdir)):
        if not fn.endswith('.tsv'):
            continue
        path = os.path.join(krdir, fn)
        with open(path, encoding='utf-8') as f:
            lines = f.read().split('\n')
        out = []
        for i, line in enumerate(lines):
            if i == 0 or not line:
                out.append(line)
                continue
            r = line.split('\t')
            if len(r) >= 7 and r[5] in single and r[6] != r[5]:
                r[6] = r[5]
                n += 1
            out.append('\t'.join(r))
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write('\n'.join(out))
    print('원문으로 되돌린 행 %d개' % n)


if __name__ == '__main__':
    main()

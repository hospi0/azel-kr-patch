# -*- coding: utf-8 -*-
"""`epk_scan2` 가 놓친 짧은 자막 16건의 번역을 `work/epk_ko.tsv` 에 추가한다.

짝(직전 자막)을 보고 «두 번째 조각»은 그 문장의 꼬리로 옮겼다
(예: 「それより、早いとこ地上に戻ろうぜ」/「に戻ろうぜ」 = 「어서 지상으로 가자」/「로 가자」).
예산은 빌더가 검사한다(선두 1바이트 토큰은 빌더가 원본에서 그대로 붙인다).
"""
import os, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'work', 'epk_ko.tsv')

ROWS = [
    ('1', 'E021.EPK', '4CFAC3', '엇?'),      # えっ？
    ('2', 'E034.EPK', '0E2D63', '주게'),      # …알려주게 의 꼬리
    ('2', 'E034.EPK', '57DADF', '아니…'),     # いや…
    ('2', 'E052.EPK', '0C68CF', '있었어'),    # 어디 있었어 의 꼬리
    ('2', 'E052.EPK', '5152C7', '에지'),      # エッジ
    ('2', 'E052.EPK', '51F87D', '에지'),      # …꼭이다,에지 의 꼬리
    ('2', 'E052.EPK', '6F1A4F', '맞나?'),     # はず？
    ('3', 'E074.EPK', '0CDE97', '핫'),        # はっ
    ('3', 'E074.EPK', '0CDE9D', '이다'),      # 진행 중이다 의 꼬리
    ('3', 'E078.EPK', '064C8B', '흐음'),      # ふーん
    ('3', 'E078.EPK', '10A50B', '안해'),      # …생각 안 해 의 꼬리
    ('3', 'E078.EPK', '213CE3', '지만'),      # …하겠지만 의 꼬리
    ('3', 'E078.EPK', '2DA9D7', '지만'),      # …알겠지만 의 꼬리
    ('3', 'E078.EPK', '50AAC3', '하지만'),    # だが…
    ('3', 'E078.EPK', 'A08BFB', '가면'),      # …노려서 가면 의 꼬리
    ('3', 'E090.EPK', '225D2B', '어라?'),     # あれ？
]


def main():
    with open(P, encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f if l.strip()]
    have = set()
    for l in lines:
        c = l.split('\t')
        if len(c) >= 3:
            have.add((c[0], c[1], c[2].upper()))
    n = 0
    for d, epk, off, ko in ROWS:
        if (d, epk, off) in have:
            print('  이미 있음: %s %s %s' % (d, epk, off))
            continue
        lines.append('\t'.join([d, epk, off, ko]))
        n += 1
    for l in lines:
        assert '\n' not in l and '\r' not in l
    with open(P, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(lines) + '\n')
    print('추가한 자막 번역 %d건 (총 %d행)' % (n, len(lines)))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""2026-11-15 용어·이름·따옴표·말투 정리(하스피 결정: ウル=우르, 나머지 추천안).

  python tools/term_unify_20261115.py          # 미리보기
  python tools/term_unify_20261115.py --apply  # ko.tsv · kr/*.tsv · epk_ko.tsv 반영(백업 *.bak_term)

원문(jp)에 그 낱말이 있는 줄만 고친다. 이름 뒤 조사는 받침에 맞춰 같이 바꾼다.
"""
import glob
import re
import shutil
import sys

N = chr(92) + 'n'
APPLY = '--apply' in sys.argv


def has_jong(ch):
    return '가' <= ch <= '힣' and (ord(ch) - 0xAC00) % 28 != 0


def is_rieul(ch):
    return '가' <= ch <= '힣' and (ord(ch) - 0xAC00) % 28 == 8


# (받침 있을 때, 없을 때) — 긴 것부터
JOSA = [('이라는', '라는'), ('이라고', '라고'), ('이에요', '예요'), ('이었', '였'), ('이야', '야'), ('이라', '라'),
        ('이랑', '랑'), ('이나', '나'), ('은', '는'), ('이', '가'), ('을', '를'), ('과', '와')]


def fix_josa(name, rest):
    """name 바로 뒤 rest 의 조사를 name 받침에 맞춘다."""
    last = name[-1]
    j = has_jong(last)
    for a, b in JOSA:
        for cur in (a, b):
            if rest.startswith(cur):
                after = rest[len(cur):len(cur) + 1]
                if after and '가' <= after <= '힣' and cur in ('이', '가', '은', '는', '을', '를', '과', '와', '이나', '나'):
                    # 「이번」「가능」 같은 다른 낱말일 수 있다 — 한 글자 조사 뒤에 한글이 이어지면 건드리지 않음
                    if cur not in ('이라', '이야'):
                        return rest
                want = a if j else b
                return want + rest[len(cur):]
    # 으로/로 — ㄹ 받침은 «로»
    for cur in ('으로', '로'):
        if rest.startswith(cur):
            want = '으로' if (j and not is_rieul(last)) else '로'
            return want + rest[len(cur):]
    return rest


FOLLOW = ('이라는', '라는', '이라고', '라고', '이에요', '예요', '이었', '였', '이야', '야', '이라', '라', '이랑', '랑',
          '이나', '나', '은', '는', '이', '가', '을', '를', '과', '와', '으로', '로', '에서', '에게', '에', '의', '도',
          '만', '인', '일', '란', '까지', '부터', '처럼', '보다', '같', '님', '들')


def rename(ko, old, new):
    i = 0
    while True:
        k = ko.find(old, i)
        if k < 0:
            return ko
        e = k + len(old)
        nxt = ko[e:e + 1]
        # 앞이 한글이면 다른 낱말의 일부(라울), 뒤가 조사 아닌 한글이면 다른 낱말(울창)
        if (k > 0 and '가' <= ko[k - 1] <= '힣') or \
                ('가' <= nxt <= '힣' and not ko[e:].startswith(FOLLOW)):
            i = e
            continue
        ko = ko[:k] + new + fix_josa(new, ko[e:])
        i = k + len(new)


# (원문 조건 정규식, 옛 표기, 새 표기)
NAMES = [
    (r'(?<![ァ-ヺ])ウル(?![ァ-ヺー])', '울', '우르'),
    (r'グリグオリグ', '그리고리그', '그리그오리그'),
    (r'メル=カヴァ', '메르카바', '멜=카바'),
    (r'マサーン', '마사안', '마산'),
    (r'シフレ', '시플레', '시프레'),
    (r'ヴェラト', '벨라토', '베라토'),
    (r'ヴェロクス', '벨록스', '베록스'),
    (r'ヴェロキタ', '벨로키타', '베로키타'),
    (r'タルメラン', '타르메란', '탈메란'),
    (r'タルバーニ', '타르바니', '탈바니'),
    (r'デルメラン', '데르메란', '델메란'),
    (r'デルバーニ', '데르바니', '델바니'),
    (r'アトルム', '아톨름', '아트룸'),
    (r'発掘所', '발굴장', '발굴소'),
    (r'発掘所', '발굴지', '발굴소'),
    (r'辺境', '변방', '변경'),
    (r'外周部', '외곽', '외주부'),
    (r'道具屋', '도구상', '도구점'),
    (r'書物', '서책', '서적'),
    (r'万象', '만상', '만물'),
    (r'攻性生物', '공성 생물', '공성생물'),
]

# 통째 문자열 치환(원문 조건, 옛, 새) — 따옴표·護り火·編み人
LITERAL = [
    ('編み人', '「편직인」', '「엮는 자」'),
    ('編み人', '"직조인" 자독', '「엮는 자」 자독'),
    ('探索兵', '"탐색병"', '「탐색병」'),
    ('探索兵', "'탐색병'", '「탐색병」'),
    ('守人', '"수호인"', '「수호인」'),
    ('メル=カヴァ', "'멜=카바'", '「멜=카바」'),
    ('護り火', "'수호의 불'", '「수호의 불」'),
    ('番人', "'파수꾼'", '「파수꾼」'),
    ('重力の道', "'중력의 길'", '「중력의 길」'),
    ('護り火」の話', '「수호의 불씨」이야기', '「수호의 불」 이야기'),
    ('「『護り火』の火種」', '「『수호의 불씨』의 불씨」', '「『수호의 불』의 불씨」'),
    ('「護り火」の火種に触れた', '「수호의 불씨」에 닿은', '「수호의 불」 불씨에 닿은'),
]

# 말투(원문 존댓말 ↔ 번역) — 원문 전체 일치 → 새 번역
TONE = {
    'おかげで、病気が治りそうです…': '덕분에 병이 나을 것 같아요…',
    'ここは、私達の村にどこか似ています…': '여기는 우리 마을과 어딘가 닮았어요…',
    'これも、ドラゴンが現れたせいでしょう': '이것도,드래곤이 나타난 탓이겠죠',
    '塔が目覚めた以上、戦いはさけられません': '탑이 깨어난 이상 싸움은 못 피해요',
    '攻性生物と…グリグオリグ、両方です': '공성생물과…그리그오리그,둘 다예요',
    '新たな実りを探しているのでしょう？': '새로운 결실을 찾고 있는 거겠죠?',
    '輪形陣に穴が開きました': '윤형진에 구멍이 뚫렸습니다',
    'ほんとに、ありがとうよ': '정말,고마워',
    '俺、結局足手まといだったね…': '나,결국 짐만 됐네…',
}


def fix(jp, ko):
    if jp in TONE:
        return TONE[jp]
    for pat, old, new in NAMES:
        if re.search(pat, jp) and old in ko:
            ko = rename(ko, old, new)
    for cond, old, new in LITERAL:
        if cond in jp and old in ko:
            ko = ko.replace(old, new)
    return ko


def run():
    changed = {}
    # ko.tsv
    L = open('work/trans/ko.tsv', encoding='utf-8').read().split('\n')
    for i, l in enumerate(L):
        p = l.split('\t')
        if len(p) < 2 or not p[1] or p[1] == p[0]:
            continue
        nk = fix(p[0], p[1])
        if nk != p[1]:
            changed[p[0]] = (p[1], nk)
            p[1] = nk
            L[i] = '\t'.join(p)
    for jp, (a, b) in changed.items():
        print('● %s\n    %s\n  → %s' % (jp[:60], a[:90], b[:90]))
    print('ko.tsv 바뀔 줄 %d' % len(changed))
    # epk_ko.tsv: 열 = 디스크·파일·오프셋·번역 — 원문은 epk_units.tsv 에서
    jp_of = {}
    for l in open('work/epk_units.tsv', encoding='utf-8').read().split('\n'):
        q = l.split('\t')
        if len(q) >= 7:
            jp_of[(q[1], q[2])] = q[6]
    E = open('work/epk_ko.tsv', encoding='utf-8').read().split('\n')
    ne = 0
    for i, l in enumerate(E):
        q = l.split('\t')
        if len(q) >= 4 and (q[1], q[2]) in jp_of:
            nk = fix(jp_of[(q[1], q[2])], q[3])
            if nk != q[3]:
                print('● EPK %s %s\n    %s\n  → %s' % (q[1], q[2], q[3][:90], nk[:90]))
                q[3] = nk; E[i] = '\t'.join(q); ne += 1
    print('epk_ko.tsv 바뀔 줄 %d' % ne)
    if not APPLY:
        return
    shutil.copy('work/trans/ko.tsv', 'work/trans/ko.tsv.bak_term')
    shutil.copy('work/epk_ko.tsv', 'work/epk_ko.tsv.bak_term')
    shutil.copytree('work/trans/kr', 'work/trans/kr.bak_term', dirs_exist_ok=True)
    open('work/trans/ko.tsv', 'w', encoding='utf-8', newline='').write('\n'.join(L))
    open('work/epk_ko.tsv', 'w', encoding='utf-8', newline='').write('\n'.join(E))
    nk = 0
    for f in glob.glob('work/trans/kr/*.tsv'):
        K = open(f, encoding='utf-8').read().split('\n'); m = False
        for i, l in enumerate(K):
            q = l.split('\t')
            if len(q) >= 7 and q[5] in changed:
                q[6] = changed[q[5]][1]; K[i] = '\t'.join(q); m = True; nk += 1
        if m:
            open(f, 'w', encoding='utf-8', newline='').write('\n'.join(K))
    print('반영 완료 — kr 작업 파일 %d줄 맞춤, 백업 *.bak_term' % nk)


run()

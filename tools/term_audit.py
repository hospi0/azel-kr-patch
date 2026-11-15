# -*- coding: utf-8 -*-
"""번역 전수 정리용 조사(읽기만) — 고유명사·한자 용어·제어 토큰·말투.

  python tools/term_audit.py [ko.tsv] > work/term_audit.txt

A 고유명사(가타카나 낱말)·B 한자 용어: 원문 낱말 K 가 든 줄들의 번역에서
  가장 많이 나온 한글 표기 T 를 표준으로 보고, T 가 없는 줄과 그 줄의 «비슷한 표기»를 보인다.
C 토큰: 원문과 번역의 제어 코드열(<XX>, <!XX>) 차이.
D 말투: 원문 존댓말(です·ます…)인데 번역이 반말 / 그 반대, 한 줄 안 존댓말·반말 섞임.
"""
import re
import sys
from collections import Counter, defaultdict

BS_N = chr(92) + 'n'
path = sys.argv[1] if len(sys.argv) > 1 else 'work/trans/ko.tsv'
rows = []
for line in open(path, encoding='utf-8').read().split('\n'):
    p = line.split('\t')
    if len(p) >= 2 and p[1] and p[1] != p[0]:
        rows.append((p[0], p[1]))

CTRL = re.compile(r'<!?[0-9A-Fa-f]{2}>')
def plain(s):
    return CTRL.sub(' ', s).replace(BS_N, ' ')

JOSA = sorted('이 가 은 는 을 를 의 에 에서 에게 와 과 로 으로 도 만 께 한테 이나 나 이랑 랑 라 이라 야 아 이여 여 님 들'.split(), key=len, reverse=True)
def strip_josa(w):
    for j in JOSA:
        if len(w) > len(j) + 1 and w.endswith(j):
            return w[:-len(j)]
    return w

HAN = re.compile(r'[가-힣]+')
def words(ko):
    return {strip_josa(w) for w in HAN.findall(plain(ko))}

def survey(pat, minlen, title, min_rows=3):
    occ = defaultdict(list)
    for jp, ko in rows:
        for k in set(re.findall(pat, plain(jp))):
            if len(k) >= minlen:
                occ[k].append((jp, ko))
    out = []
    for k, lst in occ.items():
        if len(lst) < min_rows:
            continue
        df = Counter()
        for jp, ko in lst:
            df.update(words(ko))
        if not df:
            continue
        top, c = df.most_common(1)[0]
        if c / len(lst) < 0.5:
            continue          # 표준 표기를 못 정함(일반어·뜻 번역) — 건너뜀
        miss = [(jp, ko) for jp, ko in lst if top not in plain(ko)]
        if not miss:
            continue
        alts = Counter()
        for jp, ko in miss:
            for w in words(ko):
                if w != top and w[0] == top[0] and abs(len(w) - len(top)) <= 2:
                    alts[w] += 1
        out.append((len(miss), k, top, c, len(lst), alts, miss))
    out.sort(key=lambda x: -x[4])
    print('\n' + '=' * 70 + '\n%s — %d개 낱말' % (title, len(out)))
    for nm, k, top, c, n, alts, miss in out:
        a = ', '.join('%s(%d)' % x for x in alts.most_common(6)) or '-'
        print('\n■ %s → 「%s」 %d/%d줄  · 빠진 줄 %d · 다른 표기: %s' % (k, top, c, n, nm, a))
        for jp, ko in miss[:4]:
            print('    %s\n      → %s' % (jp[:70], ko[:70]))

survey(r'[ァ-ヺー・]{2,}', 3, 'A 고유명사(가타카나)')
survey(r'[一-龯々]{2,}', 2, 'B 한자 용어', min_rows=4)

# C 토큰
print('\n' + '=' * 70 + '\nC 제어 토큰 차이(줄바꿈 제외)')
nc = 0
for jp, ko in rows:
    a, b = CTRL.findall(jp), CTRL.findall(ko)
    if a != b:
        nc += 1
        print('  %s | %s\n      %s\n    → %s' % (' '.join(a), ' '.join(b), jp[:70], ko[:70]))
print('  계 %d줄' % nc)

# D 말투
POL_JP = re.compile(r'です|ます|ません|ました|ください|でしょう|ございま|下さい')
# 문장 끝(부호 앞 또는 줄 끝)만 본다 — 낱말 안 «요»(필요)·«니다» 속 «다» 오탐 방지
END = r'(?=[.?!…~」』)■]|$)'
POL_KO = re.compile(r'(니다|세요|십시오|요|죠)' + END)
PLAIN_KO = re.compile(r'(?<![니])(다|야|어|아|지|군|냐|자|라|해|네|걸|래|구나|거든|마)' + END)
print('\n' + '=' * 70 + '\nD 말투')
cnt = Counter()
mix, j2p, p2j = [], [], []
for jp, ko in rows:
    t = plain(ko).strip()
    if len(t) < 6:
        continue
    pk = bool(POL_KO.search(t)); nk = bool(PLAIN_KO.search(t))
    pj = bool(POL_JP.search(jp))
    if pk and nk:
        mix.append((jp, ko))
    if pj and nk and not pk:
        j2p.append((jp, ko))
    if pk and not pj and not nk and re.search(r'[だよねぞぜなさい]|だろ', jp[-6:]):
        p2j.append((jp, ko))
for title, lst in (('D1 한 줄 안 존댓말·반말 섞임', mix), ('D2 원문 존댓말 → 번역 반말', j2p), ('D3 원문 반말 → 번역 존댓말', p2j)):
    print('\n-- %s %d줄' % (title, len(lst)))
    for jp, ko in lst:
        print('    %s\n      → %s' % (jp[:80], ko[:80]))

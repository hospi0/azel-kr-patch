# -*- coding: utf-8 -*-
"""ko.tsv 손상 행 복구 (2026-08-15).

⚠사고 경위: 셸 한 줄 스크립트로 `ko.tsv` 를 «줄 번호 기준»으로 고치다가
   리터럴 `\n`(역슬래시+n) 이 실제 개행으로 들어가 행이 쪼개졌고,
   줄 번호가 밀려 **무관한 항목까지 덮어썼다**.
   → 번역표는 반드시 **키(원문) 기준**으로 고치고, 셸이 아니라 파일 스크립트로 할 것.
"""
import sys, os, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 'work', 'trans', 'ko.tsv')
BS = chr(92) + 'n'          # 파일 안의 «역슬래시 + n» 두 글자

# 원문 꼬리로 찾는다(전체 키 비교는 인코딩 함정이 많다)
TAIL_FIX = {
    'ATTACK系<03>':    ('계통마다 효과가 다름', 'ATTACK계<03>'),
    'AGILITY系<03>':   ('：다수의 적',          'AGILITY계<03>'),
    'DEFENSE系<03>':   ('：소수의 적',          'DEFENSE계<03>'),
    'SPIRITUAL系<03>': ('：가까울수록강함',      'SPIRITUAL계<03>'),
}
BIND_KEY = 'BIND(バインド)<03>'


def main():
    shutil.copyfile(P, P + '.bak9')
    old = {}
    with open(P + '.bak7', encoding='utf-8') as f:
        for i, l in enumerate(f):
            if i == 0:
                continue
            jp, _, ko = l.rstrip('\n').partition('\t')
            old[jp] = ko

    with open(P, encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f]
    head, body = lines[0], lines[1:]

    n = 0
    for i, l in enumerate(body):
        jp, _, ko = l.partition('\t')
        for tail, (left, right) in TAIL_FIX.items():
            if jp.endswith(tail) and jp.count('<03>') == 2:
                body[i] = jp + '\t' + left + BS + '<03>' + BS + right
                n += 1
        if BIND_KEY in jp and jp in old:
            body[i] = jp + '\t' + old[jp]
            n += 1
    print('복구한 행 %d개' % n)

    for l in body:
        assert '\n' not in l and '\r' not in l, repr(l[:80])
    with open(P, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join([head] + body) + '\n')

    with open(P, encoding='utf-8') as f:
        for i, l in enumerate(f, 1):
            if any(k in l for k in list(TAIL_FIX) + [BIND_KEY]):
                print(i, repr(l.rstrip('\n')))


if __name__ == '__main__':
    main()

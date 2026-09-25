# -*- coding: utf-8 -*-
"""번역문에 남은 `□` 자리표시자 정리 (2026-08-15).

원문 디코드에서 「口」가 `□`(U+25A1) 자리표시자로 들어갔고, 번역문이 그걸 그대로
물려받아 **실기 화면에 네모로 찍혔다**(실기 스샷: 「유적 출□는 코앞」).

★번역표는 **원문(키) 기준**으로만 고친다 — 줄 번호로 고치다 사고 낸 적 있다
  ([[feedback_edit_transtable_by_key_not_lineno]]).
⛔`ko == jp` 인 미해독 항목(`<!DD>通路北□` 등 4건)은 손대지 않는다 — 번역 대상이 아니다.
"""
import sys, os, shutil

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KO = os.path.join(ROOT, 'work', 'trans', 'ko.tsv')
EPK = os.path.join(ROOT, 'work', 'epk_ko.tsv')

# 원문 → 새 번역문. 글자 수는 되도록 늘리지 않는다(예산은 빌더가 검사한다).
FIX = {
    '(入□がふさがれてるみたいだ)':        '(입구가 막혀 있는 듯)',
    '(出入□を守るように飾りが置いてある)':  '(출입구를 지키듯 장식이 놓였다)',
    '塔 8階 回転通路北□':                 '탑 8층 회전통로 북문',
    '塔 8階 回転通路東□':                 '탑 8층 회전통로 동문',
    '塔 8階 回転通路西□':                 '탑 8층 회전통로 서문',
    '塔 9階 回転通路北□':                 '탑 9층 회전통로 북문',
    '塔 9階 回転通路東□':                 '탑 9층 회전통로 동문',
    '塔 9階 回転通路西□':                 '탑 9층 회전통로 서문',
    '…問題ない、あそこが出□だ…':          '…문제없다,저곳이 출구다…',
    'へっ！ でけえ□叩くじゃねえか':         '헛!말은 잘하는군',
    'エレベーター：8階 回転通路北□':       '엘리베이터: 8층 회전통로 북문',
    'エレベーター：8階 西□':              '엘리베이터: 8층 서문',
    'エレベーター：9階 東□':              '엘리베이터: 9층 동문',
    'エレベーター：9階 西□':              '엘리베이터: 9층 서문',
    'クレイメンの使った入□は':             '크레이멘이 쓴 입구는',
    '放出□閉鎖':                          '방출구폐쇄',
    '教会の入□の脇に、通路があるんだとよ':  '교회 입구 옆에,통로가 있다더군',
    '無礼な□をきいて…':                   '무례한 말을 하고…',
    '第1排気□開放':                       '제1배기구 개방',
    '第2排気□開放':                       '제2배기구 개방',
    '第3排気□開放':                       '제3배기구 개방',
    '街の入□の横にある階段を越えると':      '마을 입구 옆 계단을 넘으면',
}
# 긴 항목은 부분 치환(문장 전체를 다시 쓰면 다른 손질까지 되돌아간다)
PART = {
    'ドラゴンの主な武器は、□腔内より':      ('□강', '구강'),
    '守護地に生まれた人は、':              ('아무것도 □해서는', '아무것도 먹어서는'),
    '渓谷地帯で戦った。':                  ('바늘 내는 □를', '바늘 내는 곳을'),
    '祈りの前に食物を□にした者、':          ('음식을 □한 자', '음식을 먹은 자'),
    '粒子の噴出□を壊しておくのが、一番':    ('분출□을', '분출구를'),
}


def fix_tsv(path, ko_index):
    shutil.copyfile(path, path + '.boxbak')
    with open(path, encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f]
    n = 0
    for i, l in enumerate(lines):
        cols = l.split('\t')
        if len(cols) <= ko_index:
            continue
        jp, ko = cols[0], cols[ko_index]
        if not ko or '□' not in ko or ko == jp:
            continue
        new = None
        if jp in FIX:
            new = FIX[jp]
        else:
            for pre, (a, b) in PART.items():
                if jp.startswith(pre):
                    new = ko.replace(a, b)
                    break
        if new is None:
            print('  ⚠규칙 없음: %r' % jp[:50])
            continue
        if '□' in new:
            print('  ⚠아직 □ 남음: %r' % new[:50])
        cols[ko_index] = new
        lines[i] = '\t'.join(cols)
        n += 1
    for l in lines:
        assert '\n' not in l and '\r' not in l
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(lines) + '\n')
    return n


def main():
    print('ko.tsv  고친 항목 %d개' % fix_tsv(KO, 1))
    print('epk_ko.tsv 고친 항목 %d개' % fix_tsv(EPK, 3))
    # 되읽기 검산
    for path, idx in ((KO, 1), (EPK, 3)):
        left = []
        with open(path, encoding='utf-8') as f:
            for i, l in enumerate(f, 1):
                c = l.rstrip('\n').split('\t')
                if len(c) > idx and '□' in c[idx] and c[idx] != c[0]:
                    left.append((i, c[idx][:40]))
        print('%s 남은 □(미해독 항목 제외): %d개 %s'
              % (os.path.basename(path), len(left), left[:4]))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""「캐러밴」 → 「카라반」 (2026-08-15).

지명 상자에서 「캐」가 두 칸으로 깨져 나오는 증상의 절개용 겸 표기 교정.
- 「카라반」이 표준 한국어 표기다(캐러밴 아님).
- 카(기본 0xBB)·라(0x2F)·반(0x8F) 전부 이미 기본폰트에 있다.
- 결과가 깨끗하면 배포 기준 해결, 똑같이 깨지면 **글자와 무관한 렌더러 문제**로 확정.

★번역표는 원문(키) 기준·파일 스크립트로만 고친다
  ([[feedback_edit_transtable_by_key_not_lineno]]).
"""
import os, sys, shutil

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = [(os.path.join(ROOT, 'work', 'trans', 'ko.tsv'), 1),
           (os.path.join(ROOT, 'work', 'epk_ko.tsv'), 3)]


def main():
    total = 0
    for path, idx in TARGETS:
        if not os.path.exists(path):
            continue
        shutil.copyfile(path, path + '.carabak')
        with open(path, encoding='utf-8') as f:
            lines = [l.rstrip('\n') for l in f]
        n = 0
        for i, l in enumerate(lines):
            c = l.split('\t')
            if len(c) > idx and '캐러밴' in c[idx]:
                c[idx] = c[idx].replace('캐러밴', '카라반')
                lines[i] = '\t'.join(c)
                n += 1
        for l in lines:
            assert '\n' not in l and '\r' not in l
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write('\n'.join(lines) + '\n')
        print('%-22s %d행 수정' % (os.path.basename(path), n))
        total += n
    left = 0
    for path, idx in TARGETS:
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as f:
            for l in f:
                c = l.rstrip('\n').split('\t')
                if len(c) > idx and '캐러밴' in c[idx]:
                    left += 1
    print('총 %d행 / 남은 「캐러밴」 %d행' % (total, left))


if __name__ == '__main__':
    main()

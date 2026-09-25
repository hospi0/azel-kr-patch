# -*- coding: utf-8 -*-
"""도감 등에서 사라진 «개행」을 되살린다 (2026-08-15).

경위: 2026-08-11 세션7의 «문장부호 뒤 공백 삭제» 과정에서 번역문의 `\\n`
(역슬래시+n 두 글자)까지 같이 지워졌다. `ko.tsv.bak6`(그 작업 직전)에는
개행이 온전히 남아 있고, `bak7` 부터 사라졌다.

방법: 글자는 **현재 번역문(세션7 손질 반영본)** 을 그대로 쓰고,
      **개행 위치만** bak6 에서 옮겨 온다. 두 문자열을 difflib 로 정렬해
      bak6 의 개행 자리에 대응하는 현재 위치를 찾아 끼워 넣는다.

판정 = 「원문 jp 의 개행 수」와 같아지는 것. 예산(바이트)은 개행 1개당 1B.
"""
import os, sys, csv, shutil, difflib

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
KO = os.path.join(ROOT, 'work', 'trans', 'ko.tsv')
OLD = KO + '.bak6'
BS = chr(92) + 'n'


def load(path):
    d = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            jp, _, ko = line.rstrip('\n').partition('\t')
            d[jp] = ko
    return d


def transplant(old_ko, cur_ko):
    """old_ko 의 개행 위치를 cur_ko 에 옮긴다. 실패하면 None."""
    parts = old_ko.split(BS)
    if len(parts) < 2:
        return None
    flat = ''.join(parts)
    cuts = []
    n = 0
    for p in parts[:-1]:
        n += len(p)
        cuts.append(n)
    cur = cur_ko.replace(BS, '')
    sm = difflib.SequenceMatcher(None, flat, cur, autojunk=False)
    # flat 위치 → cur 위치
    m = {}
    for a, b, size in sm.get_matching_blocks():
        for k in range(size + 1):
            m[a + k] = b + k
    out, prev = [], 0
    for c in cuts:
        if c not in m:
            return None
        pos = m[c]
        if pos < prev:
            return None
        out.append(cur[prev:pos])
        prev = pos
    out.append(cur[prev:])
    return BS.join(out)


def main():
    apply = '--apply' in sys.argv
    cur = load(KO)
    old = load(OLD)
    units = {r['jp']: r for r in csv.DictReader(
        open(os.path.join(ROOT, 'work', 'trans', 'units.tsv'), encoding='utf-8'),
        delimiter='\t')}

    fixed, skip, same = {}, [], 0
    for jp, ko in cur.items():
        if not ko or jp not in units:
            continue
        want = jp.count(BS)
        have = ko.count(BS)
        # ★★«이미 적당히 접힌» 문장은 건드리면 안 된다 — bak6 의 줄 위치를
        #   억지로 옮기면 단어 중간에서 끊겨 오히려 나빠진다(실측으로 확인).
        #   통째로 뭉개진 것(원문보다 3줄 이상 적은 것)만 되살린다.
        if want - have < 3:
            continue
        o = old.get(jp)
        if not o or o.count(BS) != want:
            skip.append(('bak6 도 개행이 안 맞음', jp))
            continue
        new = transplant(o, ko)
        if new is None:
            skip.append(('정렬 실패', jp))
            continue
        if new.count(BS) != want:
            skip.append(('개행 수 불일치', jp))
            continue
        if new == ko:
            same += 1
            continue
        fixed[jp] = new

    print('개행이 어긋난 단위 중 복원 가능 %d개 / 불가 %d개' % (len(fixed), len(skip)))
    for why, jp in skip[:8]:
        print('   ⚠%s: %s' % (why, jp[:40]))
    if not apply:
        for jp in list(fixed)[:3]:
            print('--- 예시')
            print('   전: %s' % cur[jp][:80])
            print('   후: %s' % fixed[jp][:80])
        print('\n(--apply 를 주면 반영한다)')
        return

    shutil.copyfile(KO, KO + '.nlbak')
    with open(KO, encoding='utf-8') as f:
        lines = [l.rstrip('\n') for l in f]
    n = 0
    for i, l in enumerate(lines):
        jp, sep, ko = l.partition('\t')
        if sep and jp in fixed:
            lines[i] = jp + '\t' + fixed[jp]
            n += 1
    for l in lines:
        assert '\n' not in l and '\r' not in l
    with open(KO, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(lines) + '\n')
    print('반영 %d행 (백업 ko.tsv.nlbak)' % n)


if __name__ == '__main__':
    main()

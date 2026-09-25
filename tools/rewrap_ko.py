# -*- coding: utf-8 -*-
"""낱말이 개행으로 쪼개진 번역을 «낱말 단위»로 다시 조판한다 (2026-08-15).

경위(실기): 세이브 확인창이 「현재 있는 데이터는 사 / 라집니다」로 나왔다.
줄 폭에 맞춰 **글자 수로 잘랐기** 때문이다 — 원문은 일본어라 아무 데서나 접어도
되지만 한국어는 낱말이 깨진다.

무엇을 바꾸나
  **글자는 하나도 바꾸지 않는다. 개행 위치만 옮긴다.**
  ①줄 수 ≤ 기존 ②각 줄 ≤ 기존 최대 폭 — 둘 다 지켜야 채택한다
  ([[feedback_box_fit_two_conditions]]). 하나라도 어기면 그 항목은 **건드리지 않는다**.

쪼개짐 판정
  개행 앞뒤 조각을 이어 붙인 것이 **번역 코퍼스에 낱말로 존재**하고, 앞 조각 자체는
  낱말로 안 쓰이면 쪼개진 것이다. 문장부호로 끝난 자리는 정상이므로 뺀다.

  python rewrap_ko.py            # 검사만
  python rewrap_ko.py --apply    # work/trans/ko.tsv 갱신(백업 남김)
"""
import os, sys, re, collections, shutil, datetime

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KO = os.path.join(ROOT, 'work', 'trans', 'ko.tsv')
NL = chr(92) + 'n'                      # ko.tsv 안의 개행 표기(백슬래시 + n)
END_PUNCT = '.,!?。、！？」』…·'


def out(m):
    sys.stdout.buffer.write((str(m) + '\n').encode('utf-8', 'replace'))


def load():
    rows = []
    for line in open(KO, encoding='utf-8'):
        jp, sep, ko = line.rstrip('\n').partition('\t')
        rows.append((jp, sep, ko))
    return rows


def build_vocab(rows):
    v = collections.Counter()
    for jp, sep, ko in rows:
        if not sep or not ko.strip() or ko == jp:
            continue
        for w in re.split(r'\s+', ko.replace(NL, ' ')):
            w = re.sub(r'^[^가-힣]+|[^가-힣]+$', '', w)
            if len(w) >= 2:
                v[w] += 1
    return v


def split_points(ko, vocab):
    """낱말이 쪼개진 개행의 인덱스 목록(0-based, parts 사이)."""
    parts = ko.split(NL)
    bad = []
    for i in range(len(parts) - 1):
        a, b = parts[i], parts[i + 1]
        if not a or not b or a[-1] in END_PUNCT:
            continue
        la = re.sub(r'^[^가-힣]+', '', re.split(r'\s', a)[-1])
        fb = re.sub(r'[^가-힣]+$', '', re.split(r'\s', b)[0])
        if la and fb and vocab.get(la + fb, 0) >= 1 and vocab.get(la, 0) == 0:
            bad.append(i)
    return bad


def rewrap(ko, bad, width, maxlines):
    """개행을 낱말 경계로 다시 배치. 실패하면 None."""
    parts = ko.split(NL)
    # 쪼개진 자리는 붙이고, 그 밖의 개행은 낱말 경계였으므로 공백으로 바꾼다.
    buf = parts[0]
    for i in range(1, len(parts)):
        buf += ('' if (i - 1) in bad else ' ') + parts[i]
    words = [w for w in buf.split(' ')]
    lines, cur = [], ''
    for w in words:
        cand = w if not cur else cur + ' ' + w
        if len(cand) <= width or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > maxlines or any(len(x) > width for x in lines):
        return None
    return NL.join(lines)


def main():
    apply = '--apply' in sys.argv
    rows = load()
    vocab = build_vocab(rows)
    fixed = skipped = 0
    newrows = []
    for jp, sep, ko in rows:
        if not sep or not ko.strip() or ko == jp or NL not in ko:
            newrows.append((jp, sep, ko))
            continue
        bad = split_points(ko, vocab)
        if not bad:
            newrows.append((jp, sep, ko))
            continue
        parts = ko.split(NL)
        width = max(len(x) for x in parts)
        got = rewrap(ko, bad, width, len(parts))
        if got is None or got == ko:
            skipped += 1
            out(f'⚠건너뜀(칸 조건 불충족) | {ko[:60]}')
            newrows.append((jp, sep, ko))
            continue
        # ★글자가 바뀌면 안 된다 — 개행·공백만 다르고 나머지는 같아야 한다
        norm = lambda s: s.replace(NL, '').replace(' ', '')
        if norm(got) != norm(ko):
            skipped += 1
            out(f'⛔글자가 달라져 버림 | {ko[:40]} → {got[:40]}')
            newrows.append((jp, sep, ko))
            continue
        fixed += 1
        out(f'[{fixed}] 폭≤{width} 줄 {len(parts)}→{len(got.split(NL))}'
            f'  글자 {len(ko)}→{len(got)}')
        out(f'    전 {ko[:80]}')
        out(f'    후 {got[:80]}')
        newrows.append((jp, sep, got))

    out(f'\n재조판 {fixed}건 · 건너뜀 {skipped}건')
    if not apply:
        out('(반영하려면 --apply)')
        return
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(KO, KO + '.rewrapbak_' + stamp)
    with open(KO, 'w', encoding='utf-8') as f:
        for jp, sep, ko in newrows:
            f.write(jp + sep + ko + '\n' if sep else jp + '\n')
    out(f'반영 완료 — 백업 {KO}.rewrapbak_{stamp}')


if __name__ == '__main__':
    main()

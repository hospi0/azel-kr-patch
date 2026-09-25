# -*- coding: utf-8 -*-
"""«원본↔패치 바이트 차분»이 전부 우리가 신고한 자리 안에 있는지 검사한다.

왜
  `verify_disc.py` 는 «우리가 쓴 자리를 되읽어» 맞는지 보고, `verify_ascii.py` 는
  «우리가 덮은 자리»가 ASCII 였는지 본다. 둘 다 **자리 밖으로 새어 나간 쓰기**를
  원리상 못 본다 — 예산이 뒤 문자열을 먹거나 패딩이 넘치면
  ([[feedback_budget_eats_next_string]]) 검증은 통과하는데 실기가 깨진다.
  그래서 판정을 뒤집어 **바뀐 바이트 전부를 열거하고** 신고된 자리에 대응시킨다
  ([[feedback_untranslated_detector_byte_diff]]).

출력
  - 자리 밖에서 바뀐 구간(있으면 그 자리의 원본 바이트도 같이 — 파일명·ASCII 판별용)
  - 원본이 «파일명 꼴 ASCII»인데 바뀐 구간 (CD 로더가 FILE NOT FOUND 를 내는 원인)

사용: python verify_diff_scope.py <원본Track1> <패치Track1>
"""
import os, sys, csv, re, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from iso9660 import Iso

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES = os.path.join(REPO, 'work', 'trans', 'places.tsv')
SRC_FILE = {'MOVIE': 'MOVIE.DAT', 'MENUBK': 'MENUBK.BIN', 'COMMON': 'COMMON.DAT'}
NAME_RE = re.compile(rb'[A-Z0-9_]{1,8}\.[A-Z0-9]{1,3}')


def out(m):
    sys.stdout.buffer.write((str(m) + '\n').encode('utf-8', 'replace'))


def load_places():
    """module → [(offset, budget)]"""
    by = collections.defaultdict(list)
    with open(PLACES, encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            by[r['module']].append((int(r['offset'], 16), int(r['budget'])))
    return by


def runs(a, b):
    """바뀐 바이트를 연속 구간으로 묶는다."""
    res = []
    i, n = 0, min(len(a), len(b))
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            res.append((i, j))
            i = j
        else:
            i += 1
    return res


def main():
    io, ip = Iso(sys.argv[1]), Iso(sys.argv[2])
    mo = {p.split('/')[-1]: (l, s) for p, l, s in io.walk()}
    mp = {p.split('/')[-1]: (l, s) for p, l, s in ip.walk()}
    places = load_places()

    n_out = n_name = 0
    for mod, lst in sorted(places.items()):
        fn = SRC_FILE.get(mod, mod + '.PRG')
        if fn not in mo or fn not in mp:
            continue
        lo, so = mo[fn]
        lp, sp = mp[fn]
        a = io.read(lo, so)
        b = ip.read(lp, sp)
        if a == b:
            continue
        # 신고된 자리 = [offset, offset+budget)
        ok = []
        for off, bud in lst:
            ok.append((off, off + bud))
        ok.sort()
        merged = []
        for s, e in ok:
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))

        for s, e in runs(a, b):
            # 이 구간이 신고 자리에 온전히 들어가나
            covered = any(ms <= s and e <= me for ms, me in merged)
            if covered:
                continue
            n_out += 1
            orig = a[s:e]
            near = a[max(0, s - 24):e + 24]
            nm = NAME_RE.search(near)
            tag = ''
            if nm:
                tag = '  ★파일명 꼴: ' + nm.group().decode()
                n_name += 1
            out(f'{mod}  {s:#08x}..{e:#08x} ({e-s}B) 자리 밖{tag}')
            out(f'    원본 {orig[:32].hex()}  {orig[:32]!r}')
            out(f'    패치 {b[s:e][:32].hex()}  {b[s:e][:32]!r}')

    out(f'\n자리 밖 변경 {n_out}구간 (그중 파일명 꼴 근처 {n_name}) '
        + ('✅' if not n_out else '❌'))


if __name__ == '__main__':
    main()

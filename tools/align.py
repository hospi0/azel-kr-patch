# -*- coding: utf-8 -*-
"""JP ↔ US 문자열 정렬 — 번역 참조표를 만든다.

  python tools/align.py <PRG이름> [출력.tsv]
    예: python tools/align.py TWN_ZOAH work/align_zoah.tsv

원리
----
JP·US 는 **같은 문자열 테이블을 같은 순서로** 갖는다(§7.2). 그리고 대사 사이에
`T_SF_016.PCM` 같은 **음성 파일명이 인터리브**돼 있고 그 열이 양판 동일하다(§7.3).
그래서 파일명 열을 앵커로 잡고, 앵커 사이 대사 블록을 순서대로 짝지운다.

앵커 정렬은 `difflib.SequenceMatcher` 로 한다 — US 판이 음성을 빼거나 더한 자리가
있어서 완전 일치는 아니다(`TWN_ZOAH` 기준 일치율 0.93).

앵커 사이 개수가 안 맞는 이유
----------------------------
US 는 한 대사를 **줄 단위로 여러 문자열에 나눠** 담는다.
  JP `(It's very decorative,\n and it is certainly not portable.)`  ← 문자열 1개
  US `(It's very decorative,` + `and it is certainly not portable.)` ← 문자열 2개
그래서 블록 안 개수가 JP n : US m (대개 m ≥ n) 이다.

개수가 같으면 1:1 로 붙인다. 다르면 **글자 수 비율로 비례 분할**해 JP 개수에 맞춰
US 를 묶는다. 이건 어디까지나 **추정**이라 `~` 표시를 붙인다 — 사람이 검수해야 한다.
분할조차 못 하는 경우(한쪽이 비었거나 JP 가 더 많은 경우)는 덩어리로 내보낸다.
"""
import os
import sys
import difflib

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import fnt as fntmod
import regions
import slots
import strtab


def seq(path, fntpath, ascii_data):
    """[(off, raw, toks, kind)] — 살아 있는 문자열만, 파일 순서대로."""
    nmax = 256 + len(fntmod.parse(open(fntpath, 'rb').read()))
    data = open(path, 'rb').read()
    out = []
    for a, b, _, _, _ in regions.find(data, nmax, ascii_data=ascii_data):
        tab, _ = strtab.parse_table(data, a, nmax, lenient=True)
        tab = [e for e in tab if e[0] < b]
        live = slots.live_offsets(data, tab, a, b)
        for o, raw, t in tab:
            if o not in live or not raw:
                continue
            out.append((o, raw, t, strtab.kind(raw, t)))
    return out


def jp_text(raw, toks):
    return ''.join(basemap.ch(v) if k in ('g', 'g1')
                   else ('\\n' if v == 0x06 else ('<%02X>' % v if k == 'c' else '<!%02X>' % v))
                   for k, v in toks)


def us_text(raw, toks):
    # US 본문은 1바이트 토큰이 ASCII 글자다.
    return ''.join(chr(v) if k == 'g1'
                   else ('\\n' if v == 0x06 else
                         ('<%02X>' % v if k == 'c' else
                          ('<!%02X>' % v if k == 'x' else '{%d}' % v)))
                   for k, v in toks)


MAX_SPLIT = 6      # 비례 분할을 믿을 수 있는 블록 크기 상한


def nch(e):
    return sum(1 for k, _ in e[2] if k in ('g', 'g1')) or 1


def split_block(a, b):
    """개수가 다른 블록을 글자 수 비율로 «적은 쪽 개수»만큼의 쌍으로 묶는다.

    반환 [(jp[], us[])]. 어느 쪽이 많든 처리한다 —
    US 가 대사를 줄 단위로 쪼개 US 가 많은 경우가 흔하지만, JP 쪽이 `)` 같은 조각을
    따로 갖고 있어 JP 가 많은 경우(4:3, 2:1)도 나온다.
    """
    if not a or not b or len(a) == len(b):
        return None
    # ★큰 블록에 비례 분할을 쓰면 안 된다. 한 자리만 어긋나도 그 뒤가 전부 밀리는데,
    #   결과가 «1:1» 처럼 보여서 틀린 줄 모른다. 실제로 222:214 블록에서
    #   「1500Dn」이 한 칸 밀려 엉뚱한 JP 대사에 붙었다.
    #   잘못된 1:1 보다 정직한 덩어리가 낫다.
    if max(len(a), len(b)) > MAX_SPLIT:
        return None
    if len(a) > len(b):
        return [(y, [x]) for x, y in _split(b, a)]
    return [([x], y) for x, y in _split(a, b)]


def _split(a, b):
    """len(a) < len(b) 일 때 b 를 len(a) 덩어리로 나눈다 → [(a_i, b_slice)]."""
    ja = [nch(x) for x in a]
    ub = [nch(y) for y in b]
    jt, ut = sum(ja), sum(ub)
    out = []
    ui = 0
    acc = 0
    for i, w in enumerate(ja):
        acc += w
        # 마지막 JP 조각은 남은 US 를 전부 가져간다.
        if i == len(a) - 1:
            take = len(b) - ui
        else:
            target = acc / jt * ut
            take = 0
            s = sum(ub[:ui])
            while ui + take < len(b) - (len(a) - 1 - i) and \
                    s + sum(ub[ui:ui + take + 1]) <= target + ub[ui + take] / 2.0:
                take += 1
            take = max(1, take)
        out.append((a[i], b[ui:ui + take]))
        ui += take
    return out if ui == len(b) else None


def align(J, U):
    """[(jp[], us[])] — 앵커 사이 블록 쌍."""
    ja = [i for i, x in enumerate(J) if x[3] == 'asset']
    ua = [i for i, x in enumerate(U) if x[3] == 'asset']
    jn = [J[i][1].decode() for i in ja]
    un = [U[i][1].decode() for i in ua]
    sm = difflib.SequenceMatcher(None, jn, un, autojunk=False)

    pairs = []
    jprev = uprev = 0
    for i, j, size in sm.get_matching_blocks():
        for k in range(size):
            jj, uu = ja[i + k], ua[j + k]
            pairs.append(([e for e in J[jprev:jj] if e[3] != 'asset'],
                          [e for e in U[uprev:uu] if e[3] != 'asset']))
            jprev, uprev = jj + 1, uu + 1
    pairs.append(([e for e in J[jprev:] if e[3] != 'asset'],
                  [e for e in U[uprev:] if e[3] != 'asset']))
    return [p for p in pairs if p[0] or p[1]]


def main():
    name = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    jd, ud = 'work/jp1', 'work/us1'
    import census
    fonts = {f[:-4]: 0 for f in os.listdir(jd) if f.endswith('.FNT')}
    f = census.pair_of(name, fonts)
    if not f:
        print('짝 FNT 미확정:', name)
        return
    J = seq(os.path.join(jd, name + '.PRG'), os.path.join(jd, f + '.FNT'), False)
    U = seq(os.path.join(ud, name + '.PRG'), os.path.join(ud, f + '.FNT'), True)

    pairs = align(J, U)
    rows = []
    for a, b in pairs:
        if len(a) == len(b):
            for x, y in zip(a, b):
                rows.append(('1:1', x[0], y[0], jp_text(x[1], x[2]), us_text(y[1], y[2])))
            continue
        sp = split_block(a, b)
        if sp:
            for xs, ys in sp:
                rows.append(('~%d:%d' % (len(xs), len(ys)), xs[0][0], ys[0][0],
                             ' '.join(jp_text(x[1], x[2]) for x in xs),
                             ' '.join(us_text(y[1], y[2]) for y in ys)))
            continue
        rows.append(('%d:%d' % (len(a), len(b)),
                     a[0][0] if a else -1, b[0][0] if b else -1,
                     ' ⏎ '.join(jp_text(x[1], x[2]) for x in a),
                     ' ⏎ '.join(us_text(y[1], y[2]) for y in b)))

    tot = sum(len(a) for a, b in pairs)
    exact = sum(1 for r in rows if r[0] == '1:1')
    approx = sum(1 for r in rows if r[0].startswith('~'))
    lump = sum(1 for r in rows if not r[0].startswith('~') and r[0] != '1:1')
    print('%s: JP %d / US %d 문자열, 앵커 블록 %d개' % (name, len(J), len(U), len(pairs)))
    print('  1:1 확정 %d  |  비례분할(추정) %d  |  덩어리 %d행'
          % (exact, approx, lump))
    print('  JP 대사 %d개 중 개별 대응 %d개 (%.0f%%)'
          % (tot, exact + approx, 100.0 * (exact + approx) / tot if tot else 0))

    if not out:
        return
    with open(out, 'w', encoding='utf-8') as fp:
        fp.write('kind\tjp_off\tus_off\tjp\tus\n')
        for k, jo, uo, jt, ut in rows:
            fp.write('%s\t%s\t%s\t%s\t%s\n'
                     % (k, '%06X' % jo if jo >= 0 else '-',
                        '%06X' % uo if uo >= 0 else '-', jt, ut))
    print('  →', out)


if __name__ == '__main__':
    main()

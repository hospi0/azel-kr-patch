# -*- coding: utf-8 -*-
"""번역표 검사 — 행 정렬 · 빈 칸 · 제어토큰 · 예산.

  python tools/check_kr.py [work/trans/kr] [work/trans/units]

정답은 **실제 토큰 스트림**이다(`work/toks.pkl`, `--rebuild` 로 다시 만든다).
원문을 그 문법대로 바이트로 세면 예산과 정확히 맞는다 — 재구성 모델로 어림하면
가나가 1바이트로 들어간 자리를 2바이트로 세서 수천 건이 거짓 불일치를 낸다.

토큰 문법(§7.3, §7.7 + `strtab.py`)
    `<XX>`      제어코드 1바이트          `\\n` = 0x06
    `<!XX>`     **미해독 리드바이트 1바이트** — 글자가 아니다, 그대로 보존해야 한다
    글자        index 0x20~0x7F 면 1바이트, 아니면 2바이트

예산 판정은 배정이 아직 안 끝났으므로 상한·하한 둘로 한다.
    worst  한글을 전부 2바이트로 → 통과하면 배정과 무관하게 안전
    best   한글을 전부 1바이트로 → 이것도 넘치면 **번역문을 줄여야 한다**
"""
import os
import pickle
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import basemap

CACHE = 'work/toks.pkl'

# ★글리프 하나가 여러 «글자»로 렌더되는 합자. 글자 단위로 세면 과다 계산한다 —
#   `Dn` 은 2글자로 보이지만 장면 FNT 글리프 **하나**(2바이트)다.
#   기본폰트 `BP`(253)·`EXP`(254) + 장면 FNT 의 `Dn`·`Kn`·`Ln`.
LIG = ['EXP', 'BP', 'Dn', 'Kn', 'Ln']
TOK = re.compile(r'<!([0-9A-Fa-f]{2})>|<([0-9A-Fa-f]{2})>|\\n|(%s)|(.)'
                 % '|'.join(LIG), re.S)


def parse(text):
    """[('x'|'c'|'g', 값)] — 'x' 미해독바이트, 'c' 제어코드, 'g' 글리프."""
    out = []
    for m in TOK.finditer(text):
        if m.group(1) is not None:
            out.append(('x', m.group(1)))
        elif m.group(2) is not None:
            out.append(('c', m.group(2)))
        elif m.group(3) is not None:
            out.append(('g', m.group(3)))
        elif m.group(4) is None:
            out.append(('c', '06'))
        else:
            out.append(('g', m.group(4)))
    return out


def size(text, one_byte_ok):
    """번역문의 바이트 수(종단 포함)."""
    n = 1
    for k, v in parse(text):
        if k != 'g':
            n += 1
            continue
        idx = basemap.REVERSE_KEEP.get(v)
        if idx is not None:                 # 원본 index 를 유지하는 글자
            n += 1 if 0x20 <= idx < 0x80 else 2
        else:                               # 새로 배정할 글자(한글 등)
            n += 1 if one_byte_ok else 2
    return n


def load(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        f.readline()
        for i, line in enumerate(f, 2):
            line = line.rstrip('\n')
            if line:
                rows.append((i, line.split('\t')))
    return rows


def build_cache():
    import textmodel2
    items = textmodel2.collect('work/uniq')
    m = {}
    for it in items:
        e = m.get(it['text'])
        if e is None:
            m[it['text']] = [it['toks'], it['budget'], it['kind']]
        else:
            e[1] = min(e[1], it['budget'])
    with open(CACHE, 'wb') as f:
        pickle.dump(m, f)
    return m


def selfcheck(model):
    """★토크나이저 증명 — 원문을 다시 쪼갠 토큰 수가 실제 토큰 수와 같아야 한다.

    합자(`Dn`)를 글자 둘로 세거나 `<!XX>` 를 글자 다섯으로 세면 여기서 걸린다.
    이게 맞아야 번역문 바이트 계산도 믿을 수 있다.
    """
    bad = []
    for text, (toks, budget, kind) in model.items():
        if len(parse(text)) != len(toks):
            bad.append((text, len(parse(text)), len(toks)))
    return bad


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    krdir = args[0] if args else 'work/trans/kr'
    orgdir = args[1] if len(args) > 1 else 'work/trans/units'

    if '--rebuild' in sys.argv or not os.path.exists(CACHE):
        print('토큰 캐시를 만든다 (~30초) …')
        model = build_cache()
    else:
        model = pickle.load(open(CACHE, 'rb'))

    sc = selfcheck(model)
    print('토크나이저 자기검산: 원문 %d개 중 토큰 수 불일치 %d개'
          % (len(model), len(sc)))
    for t, a, b in sc[:5]:
        print('    %r  재쪼갬 %d ≠ 실제 %d' % (t[:30], a, b))

    # ★대조 기준은 «위치» 가 아니라 «원문» 이다. 번역표를 다시 만들면 id 가
    #   밀리므로 행 번호로 맞추면 전부 거짓 불일치가 난다(실제로 6,803건 났다).
    ref = {}
    refpath = os.path.join(os.path.dirname(krdir.rstrip('/\\')), 'units.tsv')
    if os.path.exists(refpath):
        for r in load(refpath):
            ref[r[1][5]] = r[1]

    files = sorted(f for f in os.listdir(krdir) if f.endswith('.tsv'))
    tot = done = 0
    err_align, err_col, err_empty, err_ctrl = [], [], [], []
    err_unknown, over_best, over_worst, untranslated = [], [], [], []
    has_x, seen, dup = [], {}, []

    for fn in files:
        kr = load(os.path.join(krdir, fn))

        for k, (ln, r) in enumerate(kr):
            if len(r) < 6:
                err_col.append('%s:%d 열 부족(%d개)' % (fn, ln, len(r)))
                continue
            uid, kind, bud, jp = r[0], r[1], int(r[3]), r[5]
            ko = r[6] if len(r) > 6 else ''
            if len(r) > 7:
                err_col.append('%s:%d ko 안에 탭: %r' % (fn, ln, r[6][:24]))
            tot += 1

            o = ref.get(jp)
            if ref and o is None:
                err_align.append('%s:%d 번역표에 없는 원문: %s' % (fn, ln, jp[:30]))
            elif o is not None and int(o[3]) != bud:
                err_align.append('%s:%d 예산 다름 kr=%d 표=%s | %s'
                                 % (fn, ln, bud, o[3], jp[:24]))
            if jp not in model:
                err_unknown.append('%s:%d 모델에 없는 원문: %s' % (fn, ln, jp[:28]))
            if jp in seen and seen[jp] != ko:
                dup.append('%s | %s ↔ %s' % (jp[:24], seen[jp][:20], ko[:20]))
            seen[jp] = ko

            if not ko:
                err_empty.append('%s:%d %s' % (fn, ln, jp[:24]))
                continue
            done += 1

            pj, pk = parse(jp), parse(ko)
            cj = Counter(t for t in pj if t[0] == 'c')
            ck = Counter(t for t in pk if t[0] == 'c')
            if cj != ck:
                err_ctrl.append('%s:%d 원문%s → 번역%s | %s'
                                % (fn, ln, sorted(cj.elements()),
                                   sorted(ck.elements()), jp[:22]))
            xj = [v for t, v in pj if t == 'x']
            xk = [v for t, v in pk if t == 'x']
            if xj:
                has_x.append('%s:%d <!%s> | %s → %s'
                             % (fn, ln, '><!'.join(xj), jp[:20], ko[:20]))
            if xj != xk:
                err_ctrl.append('%s:%d 미해독바이트 %s → %s | %s'
                                % (fn, ln, xj, xk, jp[:22]))

            if ko == jp and any(t[0] == 'g' and t[1] not in basemap.REVERSE_KEEP
                                for t in pj):
                untranslated.append('%s:%d %s' % (fn, ln, jp[:30]))

            w = size(ko, False)
            if w > bud:
                b = size(ko, True)
                (over_best if b > bud else over_worst).append(
                    (fn, ln, bud, b, w, jp, ko))

    def show(title, items, limit=20):
        if not items:
            return
        print('\n★%s %d건' % (title, len(items)))
        for x in items[:limit]:
            print('   ', x)
        if len(items) > limit:
            print('    … 외 %d건' % (len(items) - limit))

    print('파일 %d개 / 행 %d / 채워진 행 %d (%.1f%%)'
          % (len(files), tot, done, 100.0 * done / max(tot, 1)))

    show('행 정렬 어긋남', err_align)
    show('열 깨짐', err_col)
    show('빈 번역', err_empty, 10)
    show('제어코드·미해독바이트 불일치', err_ctrl)
    show('모델에 없는 원문', err_unknown, 10)
    show('같은 원문에 다른 번역', dup, 10)
    show('원문 그대로(미번역 의심)', untranslated, 15)

    if has_x:
        print('\n⚠미해독바이트 `<!XX>` 를 품은 행 %d건 — 이건 글자가 아니라 '
              '파서가 못 읽은 raw 바이트다. 빌더 인코더가 이 표기를 모른다.'
              % len(has_x))
        for x in has_x[:12]:
            print('   ', x)
        if len(has_x) > 12:
            print('    … 외 %d건' % (len(has_x) - 12))

    if over_worst:
        print('\n△예산 주의 %d건 — 2바이트 기준 초과, 1바이트 슬롯 배정에 기댄다'
              % len(over_worst))
        for fn, ln, bud, b, w, jp, ko in over_worst[:10]:
            print('   %s:%d 예산%3d 최선%3d 최악%3d | %s → %s'
                  % (fn, ln, bud, b, w, jp[:16], ko[:16]))
        print('    … 외 %d건' % max(0, len(over_worst) - 10))

    if over_best:
        print('\n★예산 초과(확정) %d건 — 1바이트로 다 넣어도 안 들어간다, 줄일 것'
              % len(over_best))
        for fn, ln, bud, b, w, jp, ko in over_best:
            print('   %s:%d 예산%3d 최선%3d | %s → %s'
                  % (fn, ln, bud, b, jp[:20], ko[:24]))

    bad = bool(err_align or err_col or err_ctrl or over_best)
    print('\n=> %s' % ('수정 필요' if bad else '통과'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

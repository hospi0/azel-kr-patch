# -*- coding: utf-8 -*-
"""번역 대상 텍스트를 «종류별»로 뽑는다.

  python tools/export.py work/uniq work/text

산출:
  work/text/_summary.txt        종류별 집계
  work/text/<종류>.tsv          그 종류의 전체 문자열
  work/text/_unique.tsv         중복을 묶은 «실제 번역 단위» 목록

종류 (§7 조사 결과에 맞춘 것)
--------------------------------
slot       고정 슬롯 배열 안의 선택지 메뉴 항목. **제자리 예산**이라 슬롯 크기
           (종단 포함)를 넘으면 안 된다. 같은 항목이 여러 슬롯에 반복되므로
           «가장 빡빡한 슬롯»에 맞춰야 한다.
narration  `(` 로 시작하는 지문·조사문. 화면 폭 제약만 받는다.
ui         메뉴·아이템·상점·저장 등 UI 모듈의 문자열.
dialog     그 밖의 본문 대사.
asset      `T_JB_040.PCM` 같은 **파일명 — 번역 대상이 아니다.** 건드리면 음성이 깨진다.
draft      무비 이벤트 설명 모듈(EVEEXPL 을 공유하는 `TWN_E0xx`·`TWN_JIRI` 12개).
           전부 `(未完成・将来セリフ組み込み予定)` 가 붙은 **개발용 플레이스홀더**다.
           같은 문안이 모듈마다 그대로 복제돼 있다. 번역 전에 실기에서 나오는지
           확인할 것 — 안 나오면 통째로 뺄 수 있다.
"""
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import census
import fnt as fntmod
import fntmap
import glyphdict
import regions
import slots
import strtab

UI_MODULES = {'MENUEN', 'MENUBK', 'MENU', 'ITEM', 'SHOP', 'SAVE', 'FLAGEDIT',
              'WORLD', 'WORLDMAP', 'SNDTEST', 'TITLE', 'CHANGE'}


def family(stem):
    if stem in UI_MODULES:
        return 'UI'
    for p in ('TWN_', 'FLD_', 'BTL_', 'EVT'):
        if stem.startswith(p):
            return p.rstrip('_')
    return '기타'


def render(toks, scene):
    s = []
    for k, v in toks:
        if k in ('g', 'g1'):
            if v >= 256 and scene and v - 256 < len(scene):
                s.append(scene[v - 256])
            else:
                s.append(basemap.ch(v))
        elif k == 'c':
            s.append('\\n' if v == 0x06 else '<%02X>' % v)
        else:
            s.append('<!%02X>' % v)
    return ''.join(s)


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    fonts = {f[:-4]: len(fntmod.parse(open(os.path.join(src, f), 'rb').read()))
             for f in os.listdir(src) if f.endswith('.FNT')}
    maxf = max(fonts.values())

    buckets = defaultdict(list)
    fam_ch = Counter()
    uniq = {}          # 텍스트 → [건수, 최소 예산, 종류, 첫 위치]

    for p in sorted(f for f in os.listdir(src) if f.endswith('.PRG')):
        stem = p[:-4]
        fn = census.pair_of(stem, fonts)
        nmax = 256 + (fonts[fn] if fn else maxf)
        scene = fntmap.load(fn) if fn else None
        data = open(os.path.join(src, p), 'rb').read()
        fam = family(stem)

        for a, b, _, _, _ in regions.find(data, nmax):
            tab, _ = strtab.parse_table(data, a, nmax, lenient=True)
            tab = [e for e in tab if e[0] < b]
            arrs = slots.find_slot_arrays(data, tab, a, b)
            live = slots.live_offsets(data, tab, a, b)
            slot_of = {}
            for _, step, _, items, _ in arrs:
                for o in items:
                    slot_of[o] = step

            for o, raw, t in tab:
                if o not in live or not raw:
                    continue
                nch = sum(1 for k, _ in t if k in ('g', 'g1'))
                if not nch:
                    continue
                txt = render(t, scene)
                if strtab.is_asset_name(raw):
                    kind = 'asset'
                elif census.PAIR.get(stem) == 'EVEEXPL':
                    kind = 'draft'
                elif o in slot_of:
                    kind = 'slot'
                elif txt.startswith('('):
                    kind = 'narration'
                elif fam == 'UI':
                    kind = 'ui'
                else:
                    kind = 'dialog'
                budget = slot_of.get(o, 0)
                buckets[kind].append((stem, o, len(raw) + 1, budget, nch, txt))
                if kind != 'asset':
                    fam_ch[fam] += nch
                    e = uniq.get(txt)
                    if e is None:
                        uniq[txt] = [1, budget or 10 ** 9, kind,
                                     '%s+%06X' % (stem, o), nch, len(raw) + 1]
                    else:
                        e[0] += 1
                        if budget:
                            e[1] = min(e[1], budget)

    for kind, rows in sorted(buckets.items()):
        with open(os.path.join(out, kind + '.tsv'), 'w', encoding='utf-8') as f:
            f.write('module\toffset\tbytes\tslot\tchars\ttext\n')
            for stem, o, nb, bud, nch, txt in rows:
                f.write('%s\t%06X\t%d\t%s\t%d\t%s\n'
                        % (stem, o, nb, bud or '', nch, txt))

    with open(os.path.join(out, '_unique.tsv'), 'w', encoding='utf-8') as f:
        f.write('kind\tcount\tslot_min\tbytes\tchars\tfirst\ttext\n')
        for txt, (cnt, bud, kind, first, nch, nb) in sorted(
                uniq.items(), key=lambda kv: (-kv[1][0], kv[0])):
            f.write('%s\t%d\t%s\t%d\t%d\t%s\t%s\n'
                    % (kind, cnt, '' if bud >= 10 ** 9 else bud, nb, nch, first, txt))

    lines = []
    lines.append('%-10s %8s %9s %9s  %s' % ('종류', '문자열', '글자', '고유', '비고'))
    ukind = Counter(v[2] for v in uniq.values())
    for kind in ('dialog', 'narration', 'slot', 'ui', 'draft', 'asset'):
        rows = buckets.get(kind, [])
        ch = sum(r[4] for r in rows)
        note = {'asset': '⛔번역 대상 아님 (음성 파일명)',
                'slot': '★제자리 예산 — 슬롯 크기 안에 종단까지',
                'narration': '괄호 지문',
                'ui': 'UI 모듈',
                'dialog': '본문 대사',
                'draft': '⚠개발용 미완성 플레이스홀더 (실기 확인 필요)'}[kind]
        lines.append('%-10s %8d %9d %9d  %s'
                     % (kind, len(rows), ch, ukind.get(kind, 0), note))
    tot = sum(len(v) for k, v in buckets.items() if k != 'asset')
    totch = sum(r[4] for k, v in buckets.items() if k != 'asset' for r in v)
    lines.append('-' * 62)
    lines.append('%-10s %8d %9d %9d  (중복 제외 = 실제 번역 단위)'
                 % ('번역대상', tot, totch, len(uniq)))
    lines.append('')
    lines.append('모듈 계열별 글자 수: ' + ', '.join(
        '%s %d' % kv for kv in fam_ch.most_common()))
    if 'slot' in buckets:
        st = Counter(r[3] for r in buckets['slot'])
        lines.append('슬롯 크기 분포: ' + ', '.join(
            '%dB×%d' % kv for kv in sorted(st.items(), key=lambda x: -x[1])[:8]))
    txt = '\n'.join(lines)
    open(os.path.join(out, '_summary.txt'), 'w', encoding='utf-8').write(txt + '\n')
    print(txt)


if __name__ == '__main__':
    main()

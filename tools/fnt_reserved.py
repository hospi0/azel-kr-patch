# -*- coding: utf-8 -*-
"""«번역하지 않는 문자열이 쓰는 장면 FNT 칸»을 예약 목록으로 뽑는다 (2026-08-15).

경위(실기): 도감 DATA 화면의 단위 표기가 `괴` `관` `감` 으로 깨졌다.
`MENUEN.PRG 0x1E55` 의 `81 12`(= MENUEN.FNT index 274) 는 **원본 그대로** 남아
있었는데, 그 칸에 우리가 한글을 구워 넣었기 때문이다. 274~277 은 원래
`m` `cm` `kg` 같은 **단위 글리프**(위/아래 반쪽으로 나뉜 작은 글자)였다.

빌더는 「번역이 원문과 같으면 건드리지 않는다」로 365단위를 원문 그대로 두는데,
배정기(`build_charmap`)는 장면 FNT 칸을 **0번부터 순서대로** 나눠 줄 뿐이라
그 문자열들이 아직 가리키는 칸을 빈 칸으로 본다.

판정 = 「우리가 다시 쓰지 않는 자리」의 **원본 바이트**에 들어 있는
       2바이트 토큰(index ≥ 256) 전부. 그 칸은 절대 재활용하면 안 된다.

  python fnt_reserved.py <무수정 Track1>        → work/fnt_reserved.tsv
"""
import os, sys, csv, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from iso9660 import Iso

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES = os.path.join(REPO, 'work', 'trans', 'places.tsv')
UNITS = os.path.join(REPO, 'work', 'trans', 'units.tsv')
KO = os.path.join(REPO, 'work', 'trans', 'ko.tsv')
OUT = os.path.join(REPO, 'work', 'fnt_reserved.tsv')
SRC_FILE = {'MOVIE': 'MOVIE.DAT', 'MENUBK': 'MENUBK.BIN', 'COMMON': 'COMMON.DAT'}


def rewritten_ids():
    """빌더가 실제로 덮어쓰는 unit id — build_kr 과 **같은 규칙**이어야 한다."""
    jp_of, id_of = {}, {}
    for u in csv.DictReader(open(UNITS, encoding='utf-8'), delimiter='\t'):
        jp_of[u['id']] = u['jp']
        id_of[u['jp']] = u['id']
    ids = set()
    with open(KO, encoding='utf-8') as f:
        for line in f:
            jp, sep, ko = line.rstrip('\n').partition('\t')
            if not sep or not ko or ko == jp:      # 번역이 없거나 원문과 같으면 안 건드린다
                continue
            uid = id_of.get(jp)
            if uid is not None:
                ids.add(uid)
    return ids


def scene_tokens(buf, off, bud):
    """슬롯 안의 2바이트 토큰 중 index ≥ 256 인 것."""
    out, i, end = set(), off, off + bud
    while i < end:
        v = buf[i]
        if v == 0:
            break
        if v >= 0x80:
            if i + 1 >= end:
                break
            t = ((v & 0x7F) << 8) | buf[i + 1]
            if t >= 256:
                out.add(t)
            i += 2
        else:
            i += 1                  # 1바이트 글리프 토큰·제어코드
    return out


OUT_LEN = os.path.join(REPO, 'work', 'str_len.tsv')


def str_len(buf, off, lim):
    """원문 문자열의 실제 길이(종단 포함). 못 끝나면 None.

    ★`find(b'\\x00')` 로 재면 안 된다 — 2바이트 토큰의 **뒷바이트가 0x00** 일 수
      있어 거짓 종단자를 잡는다(그렇게 재면 1,598곳으로 부풀었다).
    """
    i, end = off, off + lim
    while i < end:
        v = buf[i]
        if v == 0:
            return i - off + 1
        if v >= 0x80:
            if i + 1 >= end:
                return None
            i += 2
        else:
            i += 1
    return None


def collect_len(src):
    """{(파일, 오프셋): 원문 실제 길이} — 빌더가 «예산 자르기»의 하한으로 쓴다.

    ★예산을 «다음 자리 시작»까지 자를 때, 다음 자리가 **원문 한가운데서 시작한
      거짓 검출**이면 진짜 문자열을 잘라 버린다(TWN_CARA 0x017C5D 에서 19B 짜리를
      18B 로 잘라 예산 초과가 났다). 하한 = 원문 실제 길이.
    """
    iso = Iso(src)
    mm = {p.split('/')[-1]: (l, s) for p, l, s in iso.walk()}
    cache, out = {}, {}
    for r in csv.DictReader(open(PLACES, encoding='utf-8'), delimiter='\t'):
        fn = SRC_FILE.get(r['src'], r['module'] + '.PRG')
        if fn not in cache:
            cache[fn] = iso.read(*mm[fn]) if fn in mm else None
        buf = cache[fn]
        if buf is None:
            continue
        off, bud = int(r['offset'], 16), int(r['budget'])
        if off + bud > len(buf):
            continue
        n = str_len(buf, off, bud)
        if n is not None:
            out[(fn, off)] = n
    return out


def collect(src):
    iso = Iso(src)
    mm = {p.split('/')[-1]: (l, s) for p, l, s in iso.walk()}
    cache = {}

    def get(fn):
        if fn not in cache:
            cache[fn] = iso.read(*mm[fn]) if fn in mm else None
        return cache[fn]

    keep = rewritten_ids()
    res = collections.defaultdict(set)
    for r in csv.DictReader(open(PLACES, encoding='utf-8'), delimiter='\t'):
        if r['id'] in keep or not r['fnt']:
            continue
        buf = get(SRC_FILE.get(r['src'], r['module'] + '.PRG'))
        if buf is None:
            continue
        off, bud = int(r['offset'], 16), int(r['budget'])
        if off + bud > len(buf):
            continue
        res[r['fnt']] |= scene_tokens(buf, off, bud)
    return res


def fnt_sizes():
    import fnt as fntmod
    d = os.path.join(REPO, 'work', 'uniq')
    return {f[:-4]: len(fntmod.parse(open(os.path.join(d, f), 'rb').read()))
            for f in os.listdir(d) if f.endswith('.FNT')}


def main():
    res = collect(sys.argv[1])
    # ★index 가 그 FNT 의 글리프 수를 넘으면 «글자가 아니다» — 우리가 쓸 수
    #   없는 번호이므로 예약해봐야 의미가 없고, 통계만 부풀린다.
    sz = fnt_sizes()
    res = {fn: {i for i in v if i - 256 < sz.get(fn, 0)} for fn, v in res.items()}
    res = {fn: v for fn, v in res.items() if v}
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        f.write('fnt\tindex\n')
        for fn in sorted(res):
            for i in sorted(res[fn]):
                f.write('%s\t%d\n' % (fn, i))
    lens = collect_len(sys.argv[1])
    with open(OUT_LEN, 'w', encoding='utf-8', newline='') as f:
        f.write('file\toffset\tlen\n')
        for (fn, off), n in sorted(lens.items()):
            f.write('%s\t%06X\t%d\n' % (fn, off, n))
    print('원문 실제 길이표: %d곳 → %s'
          % (len(lens), os.path.relpath(OUT_LEN, REPO)))
    tot = sum(len(v) for v in res.values())
    print('예약할 장면 FNT 칸: %d개 / 폰트 %d개 → %s'
          % (tot, len(res), os.path.relpath(OUT, REPO)))
    for fn, v in sorted(res.items(), key=lambda kv: -len(kv[1]))[:15]:
        print('   %-12s %3d/%3d칸  %s' % (fn, len(v), sz.get(fn, 0),
                                          ' '.join(str(x) for x in sorted(v)[:14])))


if __name__ == '__main__':
    main()

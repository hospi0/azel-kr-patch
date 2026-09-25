# -*- coding: utf-8 -*-
"""빌드본에 «안 바뀐 채 남은 원문»을 바이트 차분으로 전수 확정한다.

  python tools/find_leftover.py <무수정원본Track1> <빌드본Track1> [--all]

★검출은 「추출기 런」이 아니라 **원본↔빌드 바이트 차분**으로 한다
  ([[feedback_untranslated_detector_byte_diff]]) — 추출기가 못 본 자리는
  추출기 기준으로 영원히 0건이다.

판정 순서
  ① `.FNT`·`.CGB`·`.EPK` 는 건너뛴다 — 비트맵을 문자열로 읽으면 통째로 오탐.
  ② 후보의 **진짜 시작점으로 되짚는다**([[feedback_regex_string_start_backtrace]]).
     앞쪽 널부터 다시 읽어 «끝이 같은 곳에 떨어지면» 그게 진짜 시작.
     되짚은 시작이 다르면 후보는 **꼬리조각**이므로 진짜 문자열로 바꿔 센다.
  ③ 진짜 문자열이 이미 번역됐으면(바이트가 바뀜) 덮인 것이니 제외.
  ④ 잡음 배제는 **문자열 단위**로([[feedback_detector_ratio_per_string_not_per_region]])
     - 반각 영숫자가 섞이면 바이너리
     - 작은 가나가 둘 이상 연달으면 바이너리
     - 글자가 2개 미만이면 조각

글자는 그 모듈의 **자체 `.FNT`** 로 푼다 — 한자가 안 풀리면 폰트 오배정이다
([[feedback_per_region_font_not_per_file]]).
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
from iso9660 import Iso

SKIP = ('.EPK', '.FNT', '.CGB')
SMALL = set('ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ')
ASCII = re.compile(r'[0-9A-Za-z]')
JPUNCT = set('、。「」『』！？…（）・ー')


def kind(v):
    c = basemap.ch(v) if v < 256 else None
    if c is None:
        return 'k'                       # 자체 폰트 = 한자
    if '぀' <= c <= 'ヿ':
        return 'a'                       # 가나
    if c in JPUNCT:
        return 'p'
    return 'o'


def parse(data, o, limit=200):
    """o 에서 널까지 읽어 (끝, index열). 못 읽으면 (None, None)."""
    idx = []
    i = o
    n = len(data)
    while i < n and len(idx) <= limit:
        b = data[i]
        if b == 0:
            return (i, idx) if idx else (None, None)
        if b >= 0x80:
            if i + 1 >= n:
                return None, None
            idx.append(((b & 0x7F) << 8) | data[i + 1])
            i += 2
        elif b < 0x20:
            idx.append(None)             # 제어코드
            i += 1
        else:
            idx.append(b)
            i += 1
    return None, None


def true_start(data, s, e):
    """앞쪽 널부터 다시 읽어 끝이 같으면 그게 진짜 시작."""
    p = data.rfind(b'\x00', max(0, s - 256), s)
    if p < 0 or p + 1 >= s:
        return s
    e2, idx2 = parse(data, p + 1)
    return p + 1 if e2 == e else s


def is_noise(idx, txt):
    g = [v for v in idx if v is not None]
    if len(g) < 2:
        return True
    if ASCII.search(txt):
        return True                       # 반각 영숫자 = 바이너리
    prev = False
    for c in txt:
        sm = c in SMALL
        if sm and prev:
            return True                   # 작은 가나 연속 = 바이너리
        prev = sm
    ks = [kind(v) for v in g]
    if ks.count('a') + ks.count('k') < 2:
        return True
    return False


def fonts_of(iso, ents, mod):
    tab = {}
    import glyphdict
    dic = glyphdict.build('work/uniq')
    for name in ents:
        u = name.upper()
        if not u.endswith('.FNT'):
            continue
        if not u.startswith(mod.split('.')[0][:4]):
            continue
        f = iso.read(*ents[name])
        if len(f) < 18:
            continue
        n, tag = struct.unpack_from('>HH', f, 0)
        if tag != 4 or not 0 < n < 4000:
            continue
        s = 18
        for i in range(n):
            tab.setdefault(256 + i, dic.get(f[s + i * 32:s + (i + 1) * 32]))
    return tab


def main():
    src, dst = sys.argv[1], sys.argv[2]
    a, b = Iso(src), Iso(dst)
    ents = {p.lstrip('/'): (l, s) for p, l, s in a.walk() if not p.endswith('/')}
    import glyphdict
    dic = glyphdict.build('work/uniq')

    total = []
    for name in sorted(ents):
        if name.upper().endswith(SKIP):
            continue
        lba, size = ents[name]
        da = a.read(lba, size)
        db = b.read(lba, size)
        if da == db:
            continue
        # 그 모듈이 쓰는 폰트 (같은 앞머리 4글자)
        tab = {}
        pre = name.split('.')[0][:4].upper()
        for fn in ents:
            u = fn.upper()
            if not u.endswith('.FNT') or not u.startswith(pre):
                continue
            f = a.read(*ents[fn])
            if len(f) < 18:
                continue
            n, tag = struct.unpack_from('>HH', f, 0)
            if tag != 4 or not 0 < n < 4000:
                continue
            for i in range(n):
                tab.setdefault(256 + i, dic.get(f[18 + i * 32:18 + (i + 1) * 32]))

        seen = set()
        hits = []
        i = 0
        n = len(da)
        while i < n - 3:
            if da[i] < 0x80:
                i += 1
                continue
            e, idx = parse(da, i)
            if e is None:
                i += 1
                continue
            s = true_start(da, i, e)
            i = e + 1
            if s in seen:
                continue
            seen.add(s)
            if da[s:e] != db[s:e]:
                continue                  # 번역이 들어갔다
            e2, idx2 = parse(da, s)
            if e2 != e:
                continue
            txt = ''.join('<%02X>' % 0 if v is None else
                          (basemap.ch(v) if v < 256 else (tab.get(v) or '【%d】' % v))
                          for v in idx2)
            txt = txt.replace('<00>', '')
            if is_noise(idx2, txt):
                continue
            hits.append((s, txt, any(v is not None and v >= 256 for v in idx2)))
        if hits:
            print('# %s — %d개' % (name, len(hits)))
            for s, t, hasfont in hits:
                print('   %06X %s %s' % (s, '★폰트칸사용' if hasfont else '        ', t))
            total += hits
    print('== 남은 원문 %d개 (폰트칸 쓰는 것 %d개 = 화면 파손 위험)'
          % (len(total), sum(1 for _, _, f in total if f)))


if __name__ == '__main__':
    main()

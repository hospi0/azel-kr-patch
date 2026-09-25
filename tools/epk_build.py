# -*- coding: utf-8 -*-
"""EPK 컷신 자막을 «디스크에 직접» 넣는다 — 검사·굽기.

  python tools/epk_build.py <원본Track1> [<출력Track1>]      출력 없으면 검사만

EPK 는 `.PRG` 와 문법이 같은 글리프 인덱스 스트림인데, **자체 폰트를 머리
`0x28` 에 품는다**(`.FNT` 와 같은 꼴). 폰트 칸은 **여유가 하나도 없다** —
글리프 수가 그 EPK 가 쓰는 «최대 index + 1» 과 정확히 같다. 파일 크기를
바꾸면 34MB 패키지가 깨지므로 폰트는 **늘리지 않고 덮어쓰기만** 한다.

그래서 배정은 두 층뿐이다.
    기본 폰트(전역 공유)  : 이미 구운 196자를 **그대로 재사용**한다.
                            (EPK 때문에 배정을 바꾸면 다른 화면이 다 틀어진다)
    그 EPK 자체 폰트      : 기본에 없는 글자만, 칸 수 안에서.
칸이 모자라면 그 자막은 **번역을 줄여야** 한다 — 여기서 실패로 보고한다.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import cdrom_ecc
import krglyph
from iso9660 import Iso, SECTOR, DATA_OFF, DATA_LEN

FONT_OFF = 0x28          # EPK 머리의 자체 폰트
FONT_DATA = FONT_OFF + 4 + 14
TOK = re.compile(r'<!([0-9A-F]{2})>|<([0-9A-F]{2})>|\\n|(.)', re.S)


def load_base_charmap():
    """이미 구운 배정표에서 «기본 폰트» 쪽만 + 원본 그대로 두는 칸.

    ★공백·`…`·괄호·숫자·영문은 배정표에 안 들어 있다(갈아끼우지 않으니까).
      그걸 빼먹으면 그 글자들까지 «EPK 폰트에 새로 넣어야 할 글자»로 세어져
      칸이 모자란다는 잘못된 결론이 나온다.
    """
    import basemap
    base = dict(basemap.REVERSE_KEEP)
    with open('work/charmap.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) == 3 and p[0] == 'base':
                base[p[1]] = int(p[2])
    return base


def load_targets():
    rows = []
    with open('work/epk_read.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 4:
                rows.append(p)
    # `scan_epk` 와 같은 걸러내기: E006 오검출 + 꼬리조각
    keep = []
    for i, r in enumerate(rows):
        if r[0] == 'E006.EPK':
            continue
        frag = any(i != j and r[0] == q[0] and len(r[3]) < len(q[3])
                   and r[3] in q[3] and int(r[1], 16) > int(q[1], 16)
                   for j, q in enumerate(rows))
        if not frag:                  # 꼬리조각(앞 문자열 중간부터 읽힌 것)은 뺀다
            keep.append(r)
    return keep


def main():
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    sys.path.insert(0, 'work')
    import epk_ko

    base = load_base_charmap()
    rows = load_targets()
    if len(rows) != len(epk_ko.KO):
        raise SystemExit('개수 불일치: 자막 %d개 vs 번역 %d개'
                         % (len(rows), len(epk_ko.KO)))

    iso = Iso(src)
    ents = {p.lstrip('/'): (l, s) for p, l, s in iso.walk() if not p.endswith('/')}
    data = {}
    fonts = {}
    for name in sorted({r[0] for r in rows}):
        lba, size = ents[name]
        data[name] = bytearray(iso.read(lba, size))
        n = struct.unpack_from('>H', data[name], FONT_OFF)[0]
        fonts[name] = n

    # --- 어떤 글자를 그 EPK 폰트에 넣을지 --------------------------------
    need = {}                       # EPK → 기본폰트에 없는 글자 집합
    for (name, off, ln, jp), ko in zip([(r[0], r[1], r[2], r[3]) for r in rows],
                                       epk_ko.KO):
        if not ko:
            continue
        for m in TOK.finditer(ko):
            ch = m.group(3)
            if ch and ch not in base:
                need.setdefault(name, set()).add(ch)

    scene = {}
    fail = []
    for name, chars in sorted(need.items()):
        cap = fonts[name]
        cs = sorted(chars)
        if len(cs) > cap:
            fail.append((name, len(cs), cap, cs))
        scene[name] = {c: 256 + i for i, c in enumerate(cs[:cap])}
    for name in data:
        scene.setdefault(name, {})

    print('%-10s %6s %6s %6s' % ('EPK', '폰트칸', '필요', '기본밖'))
    for name in sorted(data):
        print('%-10s %6d %6d %6d'
              % (name, fonts[name], len(scene[name]), len(need.get(name, ()))))
    if fail:
        for name, n, cap, cs in fail:
            print('★%s 폰트 칸 부족: %d글자 필요 / %d칸 — %s'
                  % (name, n, cap, ''.join(cs)))
        raise SystemExit('번역을 줄이거나 글자를 기본폰트 글자로 바꿔야 한다')

    # --- 인코딩 ---------------------------------------------------------
    edits = {}
    bad = 0
    for (r, ko) in zip(rows, epk_ko.KO):
        name, off, ln, jp = r[0], int(r[1], 16), int(r[2]), r[3]
        if not ko:
            continue
        cmap = dict(base)
        cmap.update(scene[name])
        out = bytearray()
        for m in TOK.finditer(ko):
            raw, ctrl, ch = m.group(1), m.group(2), m.group(3)
            if raw is not None:
                out.append(int(raw, 16))
            elif ctrl is not None:
                out.append(int(ctrl, 16))
            elif ch is None:
                out.append(0x06)
            else:
                idx = cmap[ch]
                out += bytes([0x80 | (idx >> 8), idx & 0xFF])
        out.append(0x00)
        if len(out) > ln:
            print('★예산 초과 %s @%06X : %d > %d  %s' % (name, off, len(out), ln, ko))
            bad += 1
            continue
        out = out[:-1] + b'\x80\x01' * ((ln - len(out)) // 2) + b'\x00'
        if len(out) != ln:
            print('★길이 안 맞음 %s @%06X : %d != %d' % (name, off, len(out), ln))
            bad += 1
            continue
        edits.setdefault(name, {})[off] = bytes(out)
    print('인코딩: %d곳 / 실패 %d' % (sum(len(v) for v in edits.values()), bad))
    if bad:
        raise SystemExit('실패가 있어 멈춘다')

    # --- 폰트 굽기 ------------------------------------------------------
    font = krglyph.load('Galmuri11')
    ng = 0
    for name, m in scene.items():
        for c, idx in m.items():
            edits.setdefault(name, {})[FONT_DATA + (idx - 256) * 32] = \
                krglyph.glyph(font, c)
            ng += 1
    print('EPK 자체 폰트 %d글리프 굽기' % ng)

    if not dst:
        print('(검사만 — 출력 경로를 주면 굽는다)')
        return

    import shutil
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copyfile(src, dst)
    fh = open(dst, 'r+b')
    iso2 = Iso(dst)
    touched = 0
    for name, ed in edits.items():
        lba, size = ents[name]
        buf = bytearray(iso2.read(lba, size))
        for o, blob in ed.items():
            buf[o:o + len(blob)] = blob
        for i in range(0, size, DATA_LEN):
            sec = lba + i // DATA_LEN
            chunk = bytes(buf[i:i + DATA_LEN]).ljust(DATA_LEN, b'\x00')
            fh.seek(sec * SECTOR)
            raw = bytearray(fh.read(SECTOR))
            if raw[DATA_OFF:DATA_OFF + DATA_LEN] == chunk:
                continue
            raw[DATA_OFF:DATA_OFF + DATA_LEN] = chunk
            fh.seek(sec * SECTOR)
            fh.write(cdrom_ecc.recalc_sector(bytes(raw)))
            touched += 1
    fh.close()
    print('섹터 %d개 갱신 → %s' % (touched, dst))


if __name__ == '__main__':
    main()

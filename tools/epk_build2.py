# -*- coding: utf-8 -*-
"""EPK 자막 넣기 — 디스크별. 폰트 칸은 «아직 원문이 쓰는 자리»를 지킨다.

  python tools/epk_build2.py <디스크번호> <원본Track1> [<출력Track1>]

★★핵심 제약: EPK 자체 폰트는 **여유 칸이 없다**(글리프 수 = 쓰는 index 수).
  그래서 칸을 한글로 덮으려면 **그 칸을 쓰는 원문이 하나도 안 남아야** 한다.
  하나라도 번역을 빼먹으면 그 자막이 한글 글리프를 참조해 쓰레기가 된다
  (실기에 「왜카?」가 그렇게 나왔다 — 短い자막 `何だ？`를 검출기가 놓쳤다).

그래서 여기서는
  ① 그 EPK 의 자막을 **전부** 다시 훑고,
  ② «번역 안 한 자막»이 쓰는 칸을 «예약»으로 표시해 건드리지 않고,
  ③ 남은 칸에만 한글을 굽는다.
기본 폰트(전 모듈 공유)는 이미 구운 배정을 그대로 쓴다 — EPK 때문에 바꾸면
다른 화면이 전부 틀어진다.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import cdrom_ecc
import epk_scan2
import krglyph
from iso9660 import Iso, SECTOR, DATA_OFF, DATA_LEN

FONT_DATA = 0x28 + 4 + 14
TOK = re.compile(r'<!([0-9A-F]{2})>|<([0-9A-F]{2})>|\\n|(.)', re.S)


def base_map():
    m = dict(basemap.REVERSE_KEEP)
    with open('work/charmap.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) == 3 and p[0] == 'base':
                m[p[1]] = int(p[2])
    return m


EXTRA_TSV = 'work/epk_extra.tsv'


def load_extra():
    """{(디스크, EPK): [(오프셋, 길이, [])]} — 스캔이 놓친 짧은 자막."""
    out = {}
    if not os.path.exists(EXTRA_TSV):
        return out
    with open(EXTRA_TSV, encoding='utf-8') as f:
        next(f)
        for line in f:
            c = line.rstrip(chr(10)).split(chr(9))
            if len(c) < 4:
                continue
            out.setdefault((c[0], c[1]), []).append((int(c[2], 16), int(c[3]), []))
    return out


EXTRA = load_extra()


def load_ko(disc):
    ko = {}
    with open('work/epk_ko.tsv', encoding='utf-8') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 4 and p[0] == str(disc) and p[3]:
                ko[(p[1], int(p[2], 16))] = p[3]
    return ko


def main():
    disc = sys.argv[1]
    src = sys.argv[2]
    dst = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith('--') \
        else None
    # ★★훑기는 반드시 «무수정 원본»으로. 이미 한 번 구운 디스크를 훑으면
    #   한글로 바뀐 자막이 검출에서 빠져(한글은 자체 폰트를 안 쓴다) 자막 수가
    #   줄고, 그러면 폰트 칸 배정이 지난번과 달라져 **먼저 쓴 글리프를 깨뜨린다**.
    #   D1 에서 실제로 11개→6개로 줄었다.
    scan_src = src
    if '--scan' in sys.argv:
        scan_src = sys.argv[sys.argv.index('--scan') + 1]
    base = base_map()
    ko = load_ko(disc)

    iso = Iso(scan_src)
    ents = {p.lstrip('/'): (l, s) for p, l, s in iso.walk() if not p.endswith('/')}
    edits = {}
    print('%-10s %5s %5s %5s %5s' % ('EPK', '자막', '번역', '예약칸', '쓸칸'))
    bad = []
    for name in sorted(n for n in ents if n.upper().endswith('.EPK')):
        data = iso.read(*ents[name])
        n = epk_scan2.nfont_of(data)
        res = epk_scan2.scan(data, n)
        # ★★2026-08-15: `epk_scan2` 는 «자체 폰트를 안 쓰는 4글자 미만» 자막을
        #   버린다(`len(idx) < 4 or kana < 3`). 그런 자막은 스캔에 안 잡히니
        #   ①번역도 안 되고 ②칸 예약도 안 돼서, 그 자막이 쓰는 기본폰트 칸이
        #   한글로 갈리면 **실기에 쓰레기가 뜬다**(E021 「えっ？」→「더최?」).
        #   → `work/epk_extra.tsv` 로 손수 찾은 짧은 자막을 합친다(`tools/epk_short.py`).
        for eo, eln, eidx in EXTRA.get((str(disc), name), ()):
            if all(eo != o for o, _, _ in res):
                res.append((eo, eln, eidx))
        res.sort()
        if not res:
            continue
        # ① 번역 안 한 자막이 쓰는 칸 = 예약
        reserved = set()
        todo = []
        for o, ln, idx in res:
            k = ko.get((name, o))
            if k:
                todo.append((o, ln, k))
            else:
                reserved |= {v - 256 for v in idx if v >= 256}
        free = [i for i in range(n) if i not in reserved]

        # ② 필요한 글자 (기본 폰트에 없는 것)
        need = []
        for _, _, k in todo:
            for m in TOK.finditer(k):
                c = m.group(3)
                if c and c not in base and c not in need:
                    need.append(c)
        scene = {c: 256 + free[i] for i, c in enumerate(need) if i < len(free)}
        print('%-10s %5d %5d %5d %5d'
              % (name, len(res), len(todo), len(reserved), len(free)))
        if len(need) > len(free):
            bad.append((name, need[len(free):]))
            continue

        # ③ 인코딩
        cmap = dict(base)
        cmap.update(scene)
        ed = {}
        for o, ln, k in todo:
            # ★진짜 시작에는 «선두 제어코드»가 붙어 있다(되짚기로 드러났다).
            #   번역문에는 그게 없으므로 원본에서 그대로 떼어 붙인다.
            #   안 붙이면 길이가 1바이트 어긋나 짝이 안 맞는다(패딩은 2바이트 단위).
            head = bytearray()
            j = o
            while j < o + ln and data[j] < 0x20 and data[j] != 0:
                head.append(data[j])
                j += 1
            out = bytearray(head)
            for m in TOK.finditer(k):
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
                bad.append((name, '예산 %d>%d %s' % (len(out), ln, k)))
                continue
            # ★원본이 «1바이트 글리프»로 시작하는 문자열이면 남는 자리가 홀수라
            #   2바이트 패딩으로 딱 못 채운다. 그럴 땐 마지막 1바이트를
            #   **원본 그대로**(= 원래 종단자 0x00) 남긴다. 우리 종단자는 그
            #   앞에 놓이므로 뒤 1바이트는 읽히지 않는다.
            lim = ln - 1 if (ln - len(out)) % 2 else ln
            out = out[:-1] + b'\x80\x01' * ((lim - len(out)) // 2) + b'\x00'
            if len(out) != lim:
                bad.append((name, '길이 %d!=%d %s' % (len(out), lim, k)))
                continue
            ed[o] = bytes(out)
        font = krglyph.load('Galmuri11')
        for c, idx in scene.items():
            ed[FONT_DATA + (idx - 256) * 32] = krglyph.glyph(font, c)
        edits[name] = ed

    if bad:
        for name, why in bad:
            print('★%s : %s' % (name, why))
        raise SystemExit('실패가 있어 멈춘다')
    print('교체 %d곳 / 파일 %d개' % (sum(len(v) for v in edits.values()), len(edits)))
    if not dst:
        print('(검사만)')
        return

    import shutil
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copyfile(src, dst)
    iso2 = Iso(dst)
    fh = open(dst, 'r+b')
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

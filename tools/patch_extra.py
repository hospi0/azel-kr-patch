# -*- coding: utf-8 -*-
"""빌더가 «안 덮은 자리»를 표로 직접 메운다.

  python tools/patch_extra.py <빌드본Track1> [--dry]

표 = `work/extra_patch.tsv`   (file · offset16 · ko)

빌더는 구간 검출로 자리를 정한다. 검출이 못 본 occurrence 는 번역이 있어도
영원히 안 들어간다(실기의 「으모모」= 미번역 `クルル`). 구간 검출을 건드리면
배정이 통째로 흔들리므로([[feedback_snapshot_charmap_with_build]]) 여기서는
**빌드가 끝난 뒤 그 빌드의 배정표(`work/charmap.tsv`)로** 자리만 메운다.

★글자→index 는 반드시 **그 빌드의 charmap** 을 쓴다. 다시 배정하면 안 된다.
★예산은 원문 길이 그대로 — 넘으면 안 쓰고 실패로 보고한다.
★패딩은 «끝에 붙은 제어코드 앞»에 넣는다([[feedback_pad_before_trailing_control_code]]).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import cdrom_ecc
from iso9660 import Iso, SECTOR, DATA_OFF, DATA_LEN

TOK = re.compile(r'<!([0-9A-F]{2})>|<([0-9A-F]{2})>|\\n|(.)', re.S)


def load_charmap():
    base, scene = {}, {}
    with open('work/charmap.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) != 3:
                continue
            if p[0] == 'base':
                base[p[1]] = int(p[2])
            else:
                scene.setdefault(p[0], {})[p[1]] = int(p[2])
    return base, scene


def orig_len(data, o):
    """원문 바이트 길이(종단자 포함)와 «선두 제어코드»."""
    head = bytearray()
    i = o
    while i < len(data) and data[i] < 0x20 and data[i] != 0:
        head.append(data[i])
        i += 1
    j = i
    while j < len(data) and data[j] != 0:
        j += 2 if data[j] >= 0x80 else 1
    return j + 1 - o, bytes(head), i


def main():
    dst = sys.argv[1]
    dry = '--dry' in sys.argv
    base, scene = load_charmap()

    rows = []
    with open('work/extra_patch.tsv', encoding='utf-8') as f:
        f.readline()
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) >= 3 and p[2]:
                rows.append((p[0], int(p[1], 16), p[2]))

    iso = Iso(dst)
    ents = {p.lstrip('/'): (l, s) for p, l, s in iso.walk() if not p.endswith('/')}
    # 모듈 → 그 모듈이 쓰는 FNT (charmap 에 이름이 있는 것 중 앞머리가 같은 것)
    edits, bad = {}, []
    for fname, off, ko in rows:
        if fname not in ents:
            bad.append((fname, off, '디스크에 없다'))
            continue
        data = iso.read(*ents[fname])
        ln, head, body = orig_len(data, off)
        pre = fname.split('.')[0][:4].upper()
        cand = [fn for fn in scene if fn.upper().startswith(pre)
                or fn.upper()[3:7] == pre[-4:]]
        cmap = dict(base)
        for fn in cand:
            for c, v in scene[fn].items():
                cmap.setdefault(c, v)
        out = bytearray(head)
        miss = []
        for m in TOK.finditer(ko):
            raw, ctrl, ch = m.group(1), m.group(2), m.group(3)
            if raw is not None or ctrl is not None:
                out.append(int(raw or ctrl, 16))
            elif ch is None:
                out.append(0x06)
            elif ch in cmap:
                v = cmap[ch]
                if v < 0x80:
                    out.append(v)
                else:
                    out += bytes([0x80 | (v >> 8), v & 0xFF])
            else:
                miss.append(ch)
        if miss:
            bad.append((fname, off, '글자 없음 %s' % ''.join(sorted(set(miss)))))
            continue
        out.append(0x00)
        if len(out) > ln:
            bad.append((fname, off, '예산 %d>%d' % (len(out), ln)))
            continue
        lim = ln - 1 if (ln - len(out)) % 2 else ln
        out = out[:-1] + b'\x80\x01' * ((lim - len(out)) // 2) + b'\x00'
        if len(out) != lim:
            bad.append((fname, off, '길이 %d!=%d' % (len(out), lim)))
            continue
        edits.setdefault(fname, {})[off] = bytes(out)
        print('   %-14s %06X  %d/%dB  %s' % (fname, off, len(out), ln, ko[:40]))

    for fname, off, why in bad:
        print('★%s %06X : %s' % (fname, off, why))
    print('메울 자리 %d곳 / 실패 %d곳' % (sum(len(v) for v in edits.values()), len(bad)))
    if bad or dry:
        return

    fh = open(dst, 'r+b')
    touched = 0
    for fname, ed in edits.items():
        lba, size = ents[fname]
        buf = bytearray(iso.read(lba, size))
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

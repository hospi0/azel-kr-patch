# -*- coding: utf-8 -*-
"""이름 입력 화면(히라가나·가타카나 페이지)을 한글로 다시 그린다.

  python tools/name_entry_kr.py [--write]

★이 화면의 글자는 폰트가 아니라 **구운 그림**이다(`NAME_ENT.SCB`, 무압축 52,864B
  = 16×16 조각 413개). [[feedback_font_slot_reuse_disproves_render]] 의 전형.
⛔영어 페이지는 건드리지 않는다(A~Z 는 KEEP 이라 이미 맞다).

칸↔조각 대응은 **VDP2 패턴네임표**(세이브스테이트 VRAM)에서 떴다.
  히라가나 = plane `0x1E000` 의 열 1~20                   격자 원점 (32,38)
  가타카나 = plane `0x1E000` 열 23~31 + `0x1E800` 열 0~9   격자 원점 (8,38)
둘 다 18열×5행, 가로세로 16px. 글자가 조각 경계에 2/8px 걸쳐 있어 칸 단위로는
못 고치고 **화면으로 되조립 → 다시 자르기** 해야 한다.

★저장되는 코드 = 원래 그 칸에 그려져 있던 가나의 «원본» 기본폰트 index.
  그래서 그 index 의 **패치된 기본폰트 글리프를 그대로 복사**하면 화면과 대사가
  픽셀 단위로 같아지고 KEEP 글자(`・` `ー`)도 저절로 맞는다.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import basemap
import cdrom_ecc
from iso9660 import Iso, SECTOR, DATA_OFF, DATA_LEN

SCB = 'NAME_ENT.SCB'
CELL = ((0, 0), (8, 0), (0, 8), (8, 8))
COLS, ROWS, PITCH = 18, 5, 16
FB = 0x1068A                       # COMMON.DAT 안 기본 폰트

HIRA = ['あいうえお', 'かきくけこ', 'さしすせそ', 'たちつてと', 'なにぬねの',
        'はひふへほ', 'まみむめも', 'や_ゆ_よ', 'らりるれろ', 'わ_を_ん',
        'ぁぃぅぇぉ', 'っゃゅょ_', 'がぎぐげご', 'ざじずぜぞ', 'だぢづでど',
        'ばびぶべぼ', 'ぱぴぷぺぽ', '・ー___']
KATA = ['アイウエオ', 'カキクケコ', 'サシスセソ', 'タチツテト', 'ナニヌネノ',
        'ハヒフヘホ', 'マミムメモ', 'ヤ_ユ_ヨ', 'ラリルレロ', 'ワ_ヲ_ン',
        'ァィゥェォ', 'ッャュョ_', 'ガギグゲゴ', 'ザジズゼゾ', 'ダヂヅデド',
        'バビブベボ', 'パピプペポ', 'ヴ・ー__']

PAGES = [
    # ★원점은 «이 스트립 안에서의» 좌표다. 히라가나 스트립이 plane 열 1 부터
    #   시작하므로 전체화면 기준 32 → 스트립 기준 16 (한 칸 밀리면 첫 열 `あ`
    #   가 그대로 남는다).
    ('히라가나', 'hira', HIRA, [(0x1E000, c) for c in range(1, 21)], 16, 38),
    ('가타카나', 'kata', KATA, [(0x1E000, c) for c in range(23, 32)]
     + [(0x1E800, c) for c in range(0, 10)], 8, 38),
]


def orig_index():
    m = {}
    for i in range(256):
        c = basemap.ch(i)
        if c and c not in m:
            m[c] = i
    return m


def main():
    write = '--write' in sys.argv
    v2 = open('work/vdp2.bin', 'rb').read()
    scb = bytearray(open('work/NAME_ENT.SCB', 'rb').read())
    oi = orig_index()

    R0 = 'F:/hospi/roms/ss roms/azel'
    D1 = 'Azel - Panzer Dragoon RPG (Japan) (Disc 1) (2M)'
    iso0 = Iso('%s/%s (Track 1).bin' % (R0, D1))
    e0 = {p.lstrip('/'): (l, s) for p, l, s in iso0.walk() if not p.endswith('/')}
    com = iso0.read(*e0['COMMON.DAT'])

    total = 0
    for name, tag, lay, cols, X0, Y0 in PAGES:
        W, H = len(cols) * 16, 10 * 16
        img = [[0] * W for _ in range(H)]
        pn = [[struct.unpack_from('>H', v2, b + r * 64 + c * 2)[0] for b, c in cols]
              for r in range(10)]
        for r in range(10):
            for n in range(len(cols)):
                g = pn[r][n] - 0x200
                if not (0 <= g < len(scb) // 128):
                    continue
                for k, (dx, dy) in enumerate(CELL):
                    o = g * 128 + k * 32
                    for y in range(8):
                        row = scb[o + y * 4:o + y * 4 + 4]
                        for i, b in enumerate(row):
                            img[r * 16 + dy + y][n * 16 + dx + i * 2] = b >> 4
                            img[r * 16 + dy + y][n * 16 + dx + i * 2 + 1] = b & 15

        from collections import Counter
        cnt = Counter()
        for y in range(Y0, Y0 + ROWS * PITCH):
            for x in range(X0, X0 + COLS * PITCH):
                cnt[img[y][x]] += 1
        # ★이 구간 팔레트는 **낮은 index 가 밝다** — 원본 가나의 획이 `1`,
        #   가장자리 안티에일리어싱이 `B·D·E` 다. 최빈값(4)을 쓰면 흐리게 나오고,
        #   `0` 은 **투명**이라 배경이 비친다. [[feedback_palette_measure_dont_guess]]
        bg = cnt.most_common(1)[0][0]                 # 0 = 투명
        ink = min(v for v in cnt if v != bg)

        # 격자 전체를 지운다 — 빈 칸에도 원본 잔상(탁점)이 남아 있다
        for col in range(COLS):
            for row in range(ROWS):
                gx, gy = X0 + col * PITCH, Y0 + row * PITCH
                for y in range(-2, PITCH):
                    for x in range(PITCH):
                        if 0 <= gy + y < H and 0 <= gx + x < W:
                            img[gy + y][gx + x] = bg
        n = 0
        for col in range(COLS):
            for row in range(ROWS):
                ch = lay[col][row]
                if ch == '_':
                    continue
                idx = oi.get(ch)
                if idx is None:
                    continue
                g = com[FB + idx * 32:FB + (idx + 1) * 32]
                gx, gy = X0 + col * PITCH, Y0 + row * PITCH
                for y in range(16):
                    v = (g[y * 2] << 8) | g[y * 2 + 1]
                    for x in range(16):
                        if (v >> (15 - x)) & 1:
                            yy, xx = gy + y + 1, gx + x
                            if 0 <= yy < H and 0 <= xx < W:
                                img[yy][xx] = ink
                n += 1
        x1, y1 = X0 + COLS * PITCH, Y0 + ROWS * PITCH
        touched = set()
        for r in range(10):
            for k2 in range(len(cols)):
                g = pn[r][k2] - 0x200
                if not (0 <= g < len(scb) // 128):
                    continue
                if k2 * 16 >= x1 or (k2 + 1) * 16 <= X0:
                    continue
                if r * 16 >= y1 or (r + 1) * 16 <= Y0:
                    continue
                for k, (dx, dy) in enumerate(CELL):
                    o = g * 128 + k * 32
                    for y in range(8):
                        for i in range(4):
                            hi = img[r * 16 + dy + y][k2 * 16 + dx + i * 2]
                            lo = img[r * 16 + dy + y][k2 * 16 + dx + i * 2 + 1]
                            scb[o + y * 4 + i] = (hi << 4) | lo
                touched.add(g)
        print('%s: 바탕%d/글자%d, 찍은 칸 %d, 고친 조각 %d개'
              % (name, bg, ink, n, len(touched)))
        total += len(touched)
        try:
            from PIL import Image
            im = Image.new('L', (W, H), 0)
            px = im.load()
            for y in range(H):
                for x in range(W):
                    px[x, y] = img[y][x] * 17
            im.resize((W * 4, H * 4), Image.NEAREST).save('work/page_%s.png' % tag)
        except ImportError:
            pass
    open('work/NAME_ENT_KR.SCB', 'wb').write(bytes(scb))
    print('총 조각 %d개 → work/NAME_ENT_KR.SCB' % total)
    if not write:
        print('(파일만 만들었다 — 디스크에 쓰려면 --write)')
        return
    for f in ['Azel - Panzer Dragoon RPG (Japan) (Disc 1) (2M)',
              'Azel - Panzer Dragoon RPG (Japan) (Disc 2) (2M)',
              'Azel - Panzer Dragoon RPG (Japan) (Disc 3) (2M)',
              'Azel - Panzer Dragoon RPG (Japan) (Disc 4) (2M, 3M)']:
        dst = '%s/%s (Track 1).bin' % (R0, f)
        iso = Iso(dst)
        ents = {p.lstrip('/'): (l, s) for p, l, s in iso.walk() if not p.endswith('/')}
        if SCB not in ents:
            continue
        lba, size = ents[SCB]
        fh = open(dst, 'r+b')
        k = 0
        for i in range(0, size, DATA_LEN):
            sec = lba + i // DATA_LEN
            chunk = bytes(scb[i:i + DATA_LEN]).ljust(DATA_LEN, b'\x00')
            fh.seek(sec * SECTOR)
            raw = bytearray(fh.read(SECTOR))
            if raw[DATA_OFF:DATA_OFF + DATA_LEN] == chunk:
                continue
            raw[DATA_OFF:DATA_OFF + DATA_LEN] = chunk
            fh.seek(sec * SECTOR)
            fh.write(cdrom_ecc.recalc_sector(bytes(raw)))
            k += 1
        fh.close()
        print('  %s : 섹터 %d개' % (f[:38], k))


if __name__ == '__main__':
    main()

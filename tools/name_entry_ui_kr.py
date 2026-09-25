# -*- coding: utf-8 -*-
"""이름 입력 화면의 «일본어 그래픽 UI» 한글화.

  python tools/name_entry_ui_kr.py [--write]

  戻る → 뒤로 / 空き → 빈칸 / 終了 → 종료   … `NAME_ENT.SCB`
  文字変更 → 문자변경                        … `NAME_ENT.CGB` 오프셋 0x2E0 (112×11 4bpp)

★★**버튼 그림이 «세 벌» 들어 있다.** 페이지마다 다른 조각을 쓰므로 한 벌만 고치면
  나머지 페이지에 원본 잔상이 남는다(실기: 가타카나 페이지는 통째로 일본어,
  영어 페이지는 «위쪽에만» 잔상 — 마지막 두 조각만 공유하기 때문).

    히라가나  위 169~175          아래 185~191   가로 밀림 0
    영어      위 401~405+174,175  아래 185~191   가로 밀림 0
    가타카나  위 387~393          아래 406~412   가로 밀림 8

  버튼은 두 글리프 행에 걸친다 — 위 행의 y11~15 + 아래 행의 y0~10 = 화면 y123~138.
★안쪽은 **28×16**(밀림+6 / +38 / +70), 사이 4px 는 구분선이라 덮으면 칸이 깨진다.
★이 구간 팔레트는 **낮은 index 가 밝다** — 바탕 `15`(검정)·글자 `1`(흰색).
  `0` 은 투명이라 배경이 비친다. [[feedback_palette_measure_dont_guess]]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import cdrom_ecc
import krglyph
from iso9660 import Iso, SECTOR, DATA_OFF, DATA_LEN

CELL = ((0, 0), (8, 0), (0, 8), (8, 8))
SETS = [
    ('히라가나', list(range(169, 176)), list(range(185, 192)), 0),
    ('영어', [401, 402, 403, 404, 405, 174, 175], list(range(185, 192)), 0),
    ('가타카나', list(range(387, 394)), list(range(406, 413)), 8),
]
LABELS = ['뒤로', '빈칸', '종료']
BTN_X = (6, 38, 70)          # 밀림 기준 안쪽 시작
BTN_W, BTN_Y, BTN_H = 28, 11, 16     # 합친 32행 이미지에서 y11~26
TXT_DY, TXT_DX, TXT_PITCH = 2, 2, 13

SPR_OFF, SPR_W, SPR_H = 0x2E0, 112, 11
SPR_TEXT_X, SPR_PITCH, SPR_TEXT = 29, 12, '문자변경'


def read_run(scb, run):
    W = len(run) * 16
    img = [[0] * W for _ in range(16)]
    for n, g in enumerate(run):
        for k, (dx, dy) in enumerate(CELL):
            o = g * 128 + k * 32
            for y in range(8):
                row = scb[o + y * 4:o + y * 4 + 4]
                for i, b in enumerate(row):
                    img[dy + y][n * 16 + dx + i * 2] = b >> 4
                    img[dy + y][n * 16 + dx + i * 2 + 1] = b & 15
    return img


def write_run(scb, run, img):
    for n, g in enumerate(run):
        for k, (dx, dy) in enumerate(CELL):
            o = g * 128 + k * 32
            for y in range(8):
                for i in range(4):
                    hi = img[dy + y][n * 16 + dx + i * 2]
                    lo = img[dy + y][n * 16 + dx + i * 2 + 1]
                    scb[o + y * 4 + i] = (hi << 4) | lo


def put(img, ch, x0, y0, ink, font):
    g = krglyph.glyph(font, ch)
    ys = [y for y in range(16) if (g[y * 2] << 8) | g[y * 2 + 1]]
    top = min(ys) if ys else 0
    for y in range(16):
        v = (g[y * 2] << 8) | g[y * 2 + 1]
        for x in range(16):
            if (v >> (15 - x)) & 1:
                yy, xx = y0 + y - top, x0 + x - 2
                if 0 <= yy < len(img) and 0 <= xx < len(img[0]):
                    img[yy][xx] = ink


def main():
    write = '--write' in sys.argv
    font = krglyph.load('Galmuri11')
    src = 'work/NAME_ENT_KR.SCB' if os.path.exists('work/NAME_ENT_KR.SCB') \
        else 'work/NAME_ENT.SCB'
    scb = bytearray(open(src, 'rb').read())
    orig = open('work/NAME_ENT.SCB', 'rb').read()

    for name, top, bot, shift in SETS:
        # 색은 «무수정 원본»에서 잰다 — 이미 고친 벌을 재면 값이 흔들린다
        oi = read_run(orig, top) + read_run(orig, bot)
        from collections import Counter
        cnt = Counter()
        for bx in BTN_X:
            for y in range(BTN_Y, BTN_Y + BTN_H):
                for x in range(shift + bx, shift + bx + BTN_W):
                    cnt[oi[y][x]] += 1
        bg = cnt.most_common(1)[0][0]
        ink = min(v for v in cnt if v)

        img = read_run(scb, top) + read_run(scb, bot)
        for bx, label in zip(BTN_X, LABELS):
            x0 = shift + bx
            for y in range(BTN_Y, BTN_Y + BTN_H):
                for x in range(x0, x0 + BTN_W):
                    img[y][x] = bg
            for i, ch in enumerate(label):
                put(img, ch, x0 + TXT_DX + i * TXT_PITCH, BTN_Y + TXT_DY, ink, font)
        write_run(scb, top, img[:16])
        write_run(scb, bot, img[16:])
        print('%s 버튼: 바탕%d/글자%d, 조각 %s + %s'
              % (name, bg, ink, top, bot))

    open('work/NAME_ENT_KR.SCB', 'wb').write(bytes(scb))

    # 스프라이트 — 文字変更 → 문자변경
    cgb = bytearray(open('work/NAME_ENT.CGB', 'rb').read())
    bpr = SPR_W // 2
    spr = [[0] * SPR_W for _ in range(SPR_H)]
    for y in range(SPR_H):
        row = cgb[SPR_OFF + y * bpr:SPR_OFF + (y + 1) * bpr]
        for i, b in enumerate(row):
            spr[y][i * 2] = b >> 4
            spr[y][i * 2 + 1] = b & 15
    sink = max(v for r in spr for v in r)
    for y in range(SPR_H):
        for x in range(SPR_TEXT_X, SPR_TEXT_X + SPR_PITCH * len(SPR_TEXT)):
            spr[y][x] = 0
    for i, ch in enumerate(SPR_TEXT):
        put(spr, ch, SPR_TEXT_X + i * SPR_PITCH, 0, sink, font)
    for y in range(SPR_H):
        for i in range(bpr):
            cgb[SPR_OFF + y * bpr + i] = (spr[y][i * 2] << 4) | spr[y][i * 2 + 1]
    open('work/NAME_ENT_KR.CGB', 'wb').write(bytes(cgb))

    try:
        from PIL import Image
        im = Image.new('L', (128, len(SETS) * 36 + 16), 0)
        px = im.load()
        for j, (name, top, bot, shift) in enumerate(SETS):
            img = read_run(scb, top) + read_run(scb, bot)
            for y in range(32):
                for x in range(112):
                    px[x + 8, j * 36 + y] = (15 - img[y][x]) * 17
        for y in range(SPR_H):
            for x in range(SPR_W):
                px[x + 8, len(SETS) * 36 + y] = spr[y][x] * 17
        im.resize((im.width * 5, im.height * 5), Image.NEAREST).save('work/ui_kr.png')
        print('미리보기 → work/ui_kr.png')
    except ImportError:
        pass
    if not write:
        print('(파일만 만들었다 — 디스크에 쓰려면 --write)')
        return

    R = 'F:/hospi/roms/ss roms/azel'
    for f in ['Azel - Panzer Dragoon RPG (Japan) (Disc 1) (2M)',
              'Azel - Panzer Dragoon RPG (Japan) (Disc 2) (2M)',
              'Azel - Panzer Dragoon RPG (Japan) (Disc 3) (2M)',
              'Azel - Panzer Dragoon RPG (Japan) (Disc 4) (2M, 3M)']:
        dst = '%s/%s (Track 1).bin' % (R, f)
        iso = Iso(dst)
        ents = {p.lstrip('/'): (l, s) for p, l, s in iso.walk() if not p.endswith('/')}
        n = 0
        fh = open(dst, 'r+b')
        for nm, blob in (('NAME_ENT.SCB', scb), ('NAME_ENT.CGB', cgb)):
            if nm not in ents:
                continue
            lba, size = ents[nm]
            for i in range(0, size, DATA_LEN):
                sec = lba + i // DATA_LEN
                chunk = bytes(blob[i:i + DATA_LEN]).ljust(DATA_LEN, b'\x00')
                fh.seek(sec * SECTOR)
                raw = bytearray(fh.read(SECTOR))
                if raw[DATA_OFF:DATA_OFF + DATA_LEN] == chunk:
                    continue
                raw[DATA_OFF:DATA_OFF + DATA_LEN] = chunk
                fh.seek(sec * SECTOR)
                fh.write(cdrom_ecc.recalc_sector(bytes(raw)))
                n += 1
        fh.close()
        print('  %s : 섹터 %d개' % (f[:38], n))


if __name__ == '__main__':
    main()

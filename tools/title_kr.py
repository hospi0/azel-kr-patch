# -*- coding: utf-8 -*-
r"""타이틀 부제 «アゼル -パンツァードラグーンRPG-» → 한글(2026-11-15 하스피 «예쁜 고해상도 한글폰트로»)
  그림 = TITLEJ.SCB(8bpp 16×16 문자 = 8×8 셀 4개, 256 B) + TITLEJ.PNB(1워드, 문자 번호 0x400~ → SCB (n-0x400)*0x80)
         평면 A(32칸) + 평면 B(앞 12칸) = 704×448. 색 = 타이틀 스테이트 CRAM 앞 256색(work/title/cram.bin).
  부제 띠 문자 88칸은 다른 자리와 공유 없음.
  ① 띠 안 «밝고 채도 낮은» 글자 화소(+1px) 를 OpenCV inpaint 로 바탕 메움
  ② 한글 명조(나눔명조)를 4배로 그려 줄여 부드럽게, 원래 글자색으로 합성 → 팔레트(쓰인 색)에서 가장 가까운 색
  python tools/title_kr.py            → 미리보기 work/title/preview_<n>.png (위 원본·아래 한글, 3배)
  python tools/title_kr.py --scb      → work/title/TITLEJ_KR.SCB (디스크 쓰기는 빌드 단계에서)"""
import os, sys, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
T = os.path.join(ROOT, 'work', 'title')
TEXT = '아젤  -팬저 드래군 RPG-'
FONT = r'C:\claude\utils\font\nanum-myeongjo\NanumMyeongjo.ttf'
BAND = (214, 230, 540, 258)          # x0,y0,x1,y1 — 부제 글자가 있는 띠
X0, CAP = 220, 13                    # 시작 x · 글자 크기
SEGS = [('아젤', 226, 40), ('-팬저 드래군 RPG-', 294, 232)]   # (글, 시작 x, 길이) — 원문 두 덩이 자리


def load():
    scb = bytearray(open(os.path.join(T, 'TITLEJ.SCB'), 'rb').read())
    pnb = open(os.path.join(T, 'TITLEJ.PNB'), 'rb').read()
    vals = struct.unpack('>%dH' % (len(pnb) // 2), pnb)
    cram = open(os.path.join(T, 'cram.bin'), 'rb').read()
    pal = np.array([[(c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3]
                    for c in struct.unpack('>256H', cram[:512])], np.int32)
    return scb, vals, pal


def cells():
    """(평면, k) → (화면 X, Y, SCB 오프셋)"""
    _, vals, _ = load()
    out = []
    for plane in range(2):
        for k in range(1024):
            X = plane * 512 + (k % 32) * 16; Y = (k // 32) * 16
            if X >= 704 or Y >= 448: continue
            out.append((X, Y, ((vals[plane * 1024 + k] & 0xFFF) - 0x400) * 0x80))
    return out


QUAD = ((0, 0), (8, 0), (0, 8), (8, 8))


def to_index(scb):
    idx = np.zeros((448, 704), np.uint8)
    for X, Y, o in cells():
        for c, (dx, dy) in enumerate(QUAD):
            cell = np.frombuffer(bytes(scb[o + 64 * c:o + 64 * c + 64]), np.uint8).reshape(8, 8)
            idx[Y + dy:Y + dy + 8, X + dx:X + dx + 8] = cell
    return idx


def from_index(scb, idx, box):
    x0, y0, x1, y1 = box
    n = 0
    for X, Y, o in cells():
        if X + 16 <= x0 or X >= x1 or Y + 16 <= y0 or Y >= y1: continue
        for c, (dx, dy) in enumerate(QUAD):
            scb[o + 64 * c:o + 64 * c + 64] = idx[Y + dy:Y + dy + 8, X + dx:X + dx + 8].astype(np.uint8).tobytes()
        n += 1
    return n


def make():
    scb, vals, pal = load()
    idx = to_index(scb)
    rgb = pal[idx].astype(np.uint8)
    x0, y0, x1, y1 = BAND
    band = rgb[y0:y1, x0:x1].astype(np.int32)
    lum = band.mean(axis=2).astype(np.float32); sat = band.max(axis=2) - band.min(axis=2)
    th = lum - cv2.morphologyEx(lum, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))   # 주변보다 밝은 가는 획
    gold = (band[:, :, 0] - band[:, :, 2]) > 60                                   # 아래 영문(금색)·로고는 지우지 않음
    m = (th > 22) & (sat < 70) & (lum > 70) & ~gold
    mask = np.zeros(idx.shape, np.uint8); mask[y0:y1, x0:x1][m] = 255
    lumall = rgb.astype(np.float32).mean(axis=2)
    sel = (mask > 0) & (lumall >= np.percentile(lumall[mask > 0], 75))
    textcol = rgb[sel].mean(axis=0)                       # 원문 획의 밝은 쪽 색
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    goldall = (rgb[:, :, 0].astype(int) - rgb[:, :, 2].astype(int)) > 60
    mask[goldall] = 0                                    # 넓힌 1px 이 금색 획을 먹지 않게
    clean = cv2.inpaint(rgb, mask, 3, cv2.INPAINT_TELEA)
    # 한글 4배 렌더 — 원문처럼 두 덩이: «아젤» / «-팬저 드래군 RPG-», 덩이마다 자기 길이에 자간 맞춤
    S = 4
    f = ImageFont.truetype(FONT, CAP * S + 6 * S)
    top = f.getbbox('가')[1]; bot = f.getbbox('가')[3]
    W, H = (SEGS[-1][1] + SEGS[-1][2] - X0) * S + 8 * S, (y1 - y0) * S
    a = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(a)
    for txt, sx, span in SEGS:
        ws = [f.getbbox(ch)[2] if ch != ' ' else f.getbbox('가')[2] * 2 // 5 for ch in txt]
        gap = max(0, (span * S - sum(ws)) / max(1, len(txt) - 1))
        x = (sx - X0 + 4) * S
        for ch, w_ in zip(txt, ws):
            if ch != ' ': d.text((x, (H - (bot - top)) // 2 - top), ch, font=f, fill=255)
            x += w_ + gap
    a = np.array(a.resize((W // S, H // S), Image.LANCZOS), np.float32) / 255
    out = clean.astype(np.float32)
    h, w = a.shape
    xs = X0 - 4
    reg = out[y0:y0 + h, xs:xs + w]
    reg[:] = reg * (1 - a[:reg.shape[0], :reg.shape[1], None]) + textcol * a[:reg.shape[0], :reg.shape[1], None]
    # 팔레트로(타이틀이 실제로 쓰는 색만)
    used = np.unique(idx)
    P = pal[used].astype(np.float32)
    box = (x0 - 8, y0 - 4, max(x1, xs + w) + 8, y1 + 4)
    bx0, by0, bx1, by1 = box
    sub = out[by0:by1, bx0:bx1]
    d = ((sub[:, :, None, :] - P[None, None, :, :]) ** 2).sum(-1)
    nidx = idx.copy(); nidx[by0:by1, bx0:bx1] = used[d.argmin(-1)]
    # 띠 밖(손대지 않을 곳)은 원래 값 유지 — 글자·메운 자리만
    keep = np.ones(idx.shape, bool); keep[by0:by1, bx0:bx1] = False
    chg = np.zeros(idx.shape, bool); chg[y0:y1, x0:max(x1, xs + w)] = True
    nidx[~chg] = idx[~chg]
    touch = mask > 0
    ta = np.zeros(idx.shape, bool); ta[y0:y0 + h, xs:xs + w] = a[:min(h, 448 - y0), :min(w, 704 - xs)] > 0.02
    touch |= ta
    nidx[~touch] = idx[~touch]                           # 지운 자리·한글 획 말고는 원본 그대로
    return scb, idx, nidx, pal, (x0, y0, max(x1, xs + w), y1)


def preview():
    scb, idx, nidx, pal, box = make()
    x0, y0, x1, y1 = box
    c = (x0 - 30, y0 - 20, x1 + 30, y1 + 22)
    a = Image.fromarray(pal[idx].astype(np.uint8)).crop(c)
    b = Image.fromarray(pal[nidx].astype(np.uint8)).crop(c)
    W, H = a.size
    im = Image.new('RGB', (W, H * 2 + 6), (255, 255, 255)); im.paste(a, (0, 0)); im.paste(b, (0, H + 6))
    n = 1
    while os.path.exists(os.path.join(T, 'preview_%d.png' % n)): n += 1
    p = os.path.join(T, 'preview_%d.png' % n)
    im.resize((W * 3, (H * 2 + 6) * 3), Image.NEAREST).save(p)
    full = Image.fromarray(pal[nidx].astype(np.uint8)); full.save(os.path.join(T, 'preview_%d_full.png' % n))
    print(p)


def write_scb():
    scb, idx, nidx, pal, box = make()
    n = from_index(scb, nidx, box)
    open(os.path.join(T, 'TITLEJ_KR.SCB'), 'wb').write(bytes(scb))
    print('문자 %d칸 → work/title/TITLEJ_KR.SCB' % n)


if __name__ == '__main__' and '--disc' not in sys.argv:
    write_scb() if '--scb' in sys.argv else preview()


def write_disc(dst):
    """TITLEJ_KR.SCB 를 디스크(트랙 1)의 TITLEJ.SCB 자리에 쓴다(같은 크기, 바뀐 섹터만 EDC/ECC 재계산)"""
    from iso9660 import Iso, SECTOR, DATA_OFF, DATA_LEN
    import cdrom_ecc
    blob = open(os.path.join(T, 'TITLEJ_KR.SCB'), 'rb').read()
    iso = Iso(dst)
    ents = {p.lstrip('/'): (l, s) for p, l, s in iso.walk() if not p.endswith('/')}
    lba, size = ents['TITLEJ.SCB']
    assert size == len(blob), (size, len(blob))
    n = 0
    with open(dst, 'r+b') as fh:
        for i in range(0, size, DATA_LEN):
            sec = lba + i // DATA_LEN
            chunk = blob[i:i + DATA_LEN].ljust(DATA_LEN, b'\0')
            fh.seek(sec * SECTOR); raw = bytearray(fh.read(SECTOR))
            if raw[DATA_OFF:DATA_OFF + DATA_LEN] == chunk: continue
            raw[DATA_OFF:DATA_OFF + DATA_LEN] = chunk
            fh.seek(sec * SECTOR); fh.write(cdrom_ecc.recalc_sector(bytes(raw))); n += 1
    print('TITLEJ.SCB 섹터 %d개 → %s' % (n, dst))


if __name__ == '__main__' and '--disc' in sys.argv:
    write_disc(sys.argv[sys.argv.index('--disc') + 1])

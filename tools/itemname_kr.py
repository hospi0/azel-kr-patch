# -*- coding: utf-8 -*-
r"""아이템·버서크 이름 한글화(2026-11-15 하스피 «아이템 이름과 기술명 한글로»)

  ■ 이름 표 = COMMON.DAT 0xC8D8~0xCF84 반각(JIS X0201) 문자열, 레코드(0xBFEC~, 12 B: 이름 포인터·설명 포인터·4 B)의
    이름 포인터(0x0020xxxx, COMMON.DAT 은 RAM 0x00200000 에 상주)로만 참조 → 구역 안에서 «길이대로» 다시 채우고 포인터를 고친다.
    끝의 특수 문자열 2개(0xCF84·0xCF8C)는 1ST_READ 가 직접 가리키므로 제자리.
  ■ 렌더러 = 1ST_READ.PRG 0x060255DC 반각→글리프 변환(출력 0x8000+index 워드). 원래 0x80~0x9F 는 «영문(+125)» 갈래로 빠짐.
    → 영문 갈래 입구(0x0602561E) 8 B 를 «동굴로 점프»로 바꾸고, 동굴에서
       ① b < 65  → 원래 다음 판정(0x06025628, mov r5,r0 재현)
       ② 0x80 ≤ b ≤ 0x9F → 2바이트 글리프 토큰 그대로(b<<8 | 다음 바이트) 저장 → 0x06025668
       ③ 나머지(영문) → add #125 → 0x06025664 (원래대로)
    동굴 코드 = 이름 구역 끝 남는 자리(COMMON.DAT, RAM 0x0020xxxx). R2 만 씀(이 함수가 안 쓰는 레지스터).
  ■ 한글 글자는 «기본 폰트» 2바이트 토큰(80 xx)만 — 이름은 어느 화면에서나 그려지므로(build_kr 가 must_base 로 강제).
    숫자·영문 대문자·공백·-·? 는 원래 반각 1바이트(변환 함수의 고정 칸).
  표: work/trans/items_kr.tsv (off·jp·ko, ko 빈칸 = 원문 그대로)"""
import os, struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, 'work', 'trans', 'items_kr.tsv')
REG_LO, REG_HI = 0xC8D8, 0xCF84          # 다시 채우는 구역(끝 특수 문자열 앞까지)
REC_LO, REC_HI = 0xBF00, 0xC8D8          # 이름 포인터를 찾는 레코드 구역
RAM = 0x00200000
ITEM_WIDTH = 8                           # 화면 칸(실기: 9자는 수량 x 에 붙음)
ASCII_OK = set('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ -?')

# 1ST_READ.PRG (로드 0x06006000)
FR_BASE = 0x06006000
HOOK = 0x0602561E
HOOK_ORIG = bytes.fromhex('3573 8B01 A01F 757D 6053'.replace(' ', ''))   # cmp/ge r7,r5 · bf · bra · add #125 · mov r5,r0
CONT, STORE, NEXT = 0x06025628, 0x06025664, 0x06025668


def rows():
    out = []
    for ln, line in enumerate(open(TSV, encoding='utf-8')):
        if ln == 0: continue
        p = line.rstrip('\n').split('\t')
        out.append((int(p[0], 16), p[1], p[2] if len(p) > 2 else ''))
    return out


def chars():
    return {c for _, _, ko in rows() for c in ko if '가' <= c <= '힣'}


def _orig_name(cd, off):
    e = cd.index(b'\0', off)
    return cd[off:e + 1]


def cave_code(cave):
    """동굴 기계어(cave = RAM 주소, 4 정렬). 위 갈래 ①②③."""
    assert cave % 4 == 0
    lit = cave + 48                                  # 리터럴 3개(4 정렬)
    def movl(pc, ea):                                # mov.l @(disp,PC),R2
        d = (ea - ((pc + 4) & ~3)) // 4
        assert 0 <= d < 256 and ea == ((pc + 4) & ~3) + 4 * d, (hex(pc), hex(ea))
        return 0xD200 | d
    def bf(pc, tgt):
        d = (tgt - (pc + 4)) // 2
        assert -128 <= d < 128
        return 0x8B00 | (d & 0xFF)
    w = [0] * 24
    w[0] = 0x3573                     # +0  cmp/ge r7,r5      (r7 = 65)
    w[1] = bf(cave + 2, cave + 40)    # +2  bf Lsmall
    w[2] = 0x6053                     # +4  mov r5,r0
    w[3] = 0x4009                     # +6  shlr2 r0
    w[4] = 0x4009                     # +8  shlr2 r0
    w[5] = 0x4001                     # +10 shlr r0           (r0 = b>>5)
    w[6] = 0x8804                     # +12 cmp/eq #4,r0      (0x80~0x9F)
    w[7] = bf(cave + 14, cave + 32)   # +14 bf Lupper
    w[8] = 0x4518                     # +16 shll8 r5
    w[9] = 0x6044                     # +18 mov.b @r4+,r0
    w[10] = 0x600C                    # +20 extu.b r0,r0
    w[11] = 0x250B                    # +22 or r0,r5
    w[12] = 0x2D51                    # +24 mov.w r5,@r13
    w[13] = movl(cave + 26, lit + 0)  # +26 mov.l NEXT,r2
    w[14] = 0x422B                    # +28 jmp @r2
    w[15] = 0x0009                    # +30 nop
    w[16] = 0x757D                    # +32 Lupper: add #125,r5
    w[17] = movl(cave + 34, lit + 4)  # +34 mov.l STORE,r2
    w[18] = 0x422B                    # +36 jmp @r2
    w[19] = 0x0009                    # +38 nop
    w[20] = 0x6053                    # +40 Lsmall: mov r5,r0
    w[21] = movl(cave + 42, lit + 8)  # +42 mov.l CONT,r2
    w[22] = 0x422B                    # +44 jmp @r2
    w[23] = 0x0009                    # +46 nop
    return b''.join(struct.pack('>H', x) for x in w) + struct.pack('>III', NEXT, STORE, CONT)


def hook_code(cave):
    """1ST_READ 0x0602561E 에 쓸 10 B: mov.l @(1,PC),r2 · jmp @r2 · nop · .long cave"""
    return struct.pack('>HHHI', 0xD201, 0x422B, 0x0009, cave)


# ■ 이름 전용 글꼴(기본 폰트에 없는 음절) — 글자 번호 0x1000+n, 토큰 `90 nn`
#   글리프 캐시 적재 함수(1ST_READ 0x0602606E)의 «번호→글꼴 데이터» 갈래(0x06026094~0x060260A7)를 동굴로 돌려
#   번호 ≥ 0x1000 이면 이름 글꼴(행 1~11, 22 B)을 32 B 작업 칸 1~11행에 복사해 그 칸을 글리프로 넘긴다.
#   이름 글꼴·동굴·작업 칸 = IP.BIN 뒤쪽(RAM 0x06005200~, 12개 화면 스테이트 모두 0 · 상주 모듈 참조 0).
#   IP.BIN 은 BIOS 가 부팅 때 크기(0xE0)만큼 0x06002000 에 올린다 → 크기를 늘려 같이 싣는다.
NAME_BASE = 0x1000
IP_RAM = 0x06002000
NF_RAM = 0x06005200                 # 이 구역 시작(파일 0x3200)
NF_END = 0x06005A00                 # 위쪽은 스택으로 보임(0x06005A00~ 사용 흔적) — 넘기면 실패
LOAD_HOOK = 0x06026094
LOAD_HOOK_ORIG = bytes.fromhex('88048F12251997063573890DD3056632A00B5663')
LOAD_BACK = 0x060260BE
BASE_PTR = 0x060525E0


def load_cave(cave, nf, scratch):
    """캐시 적재 동굴. 들어올 때 r0 = 장면 글꼴 표지 바이트, r1 = 0xFFFF, r5 = 번호(마스크 전), r6 = 장면 글리프,
    r2·r3·r7 자유(원래 코드가 뒤에서 다시 씀). 나갈 때 r5 = 글리프 번호, r6 = 글리프 데이터 → 0x060260BE"""
    assert cave % 4 == 0
    W = {}
    code = []
    def emit(x): code.append(x)
    labels = {}
    fix = []                                  # (위치, 종류, 대상)
    def here(): return cave + 2 * len(code)
    # 리터럴은 코드 뒤
    emit(0x2519)                               # and r1,r5
    fix.append((len(code), 'lit', 'L1000')); emit(0xD300)   # mov.l L1000,r3
    emit(0x3532)                               # cmp/hs r3,r5
    fix.append((len(code), 'bt', 'NAME')); emit(0x8900)
    emit(0x8804)                               # cmp/eq #4,r0
    fix.append((len(code), 'bf', 'OUT')); emit(0x8B00)
    emit(0xE301); emit(0x4318)                 # r3 = 256
    emit(0x3533)                               # cmp/ge r3,r5
    fix.append((len(code), 'bt', 'SCENE')); emit(0x8900)
    fix.append((len(code), 'lit', 'LE0')); emit(0xD300)     # mov.l BASE_PTR,r3
    emit(0x6632); emit(0x5663)                 # r6 = *(r3) ; r6 = @(0C,r6)
    fix.append((len(code), 'bra', 'OUT')); emit(0xA000); emit(0x0009)
    labels['SCENE'] = len(code)
    emit(0x3538)                               # sub r3,r5
    fix.append((len(code), 'bra', 'OUT')); emit(0xA000); emit(0x0009)
    labels['NAME'] = len(code)
    emit(0x3538)                               # sub r3,r5  (n)
    emit(0x6053); emit(0x4000); emit(0x6303); emit(0x4000); emit(0x330C); emit(0x4008); emit(0x330C)  # r3 = 22n
    fix.append((len(code), 'lit0', 'LNF')); emit(0xD000)    # mov.l NF,r0
    emit(0x330C)                               # r3 += NF
    fix.append((len(code), 'lit6', 'LSCR')); emit(0xD600)   # mov.l SCR,r6
    emit(0xE70B)                               # mov #11,r7
    emit(0x6263); emit(0x7202)                 # r2 = r6 + 2
    labels['LOOP'] = len(code)
    emit(0x6035); emit(0x2201); emit(0x7202); emit(0x4710)  # mov.w @r3+,r0 · mov.w r0,@r2 · add #2,r2 · dt r7
    fix.append((len(code), 'bf', 'LOOP')); emit(0x8B00)
    emit(0xE500)                               # r5 = 0
    labels['OUT'] = len(code)
    fix.append((len(code), 'lit', 'LBE')); emit(0xD300)
    emit(0x432B); emit(0x0009)
    if len(code) % 2: emit(0x0009)
    lits = {'L1000': NAME_BASE, 'LE0': BASE_PTR, 'LNF': nf, 'LSCR': scratch, 'LBE': LOAD_BACK}
    lit_at = {}
    base_lit = cave + 2 * len(code)
    for k, (name, v) in enumerate(lits.items()): lit_at[name] = base_lit + 4 * k
    for pos, kind, tgt in fix:
        pc = cave + 2 * pos
        if kind.startswith('lit'):
            ea = lit_at[tgt]; d = (ea - ((pc + 4) & ~3)) // 4
            assert 0 <= d < 256 and ((pc + 4) & ~3) + 4 * d == ea
            code[pos] |= d
        else:
            t = cave + 2 * labels[tgt]
            d = (t - (pc + 4)) // 2
            if kind == 'bra':
                assert -2048 <= d < 2048; code[pos] |= d & 0xFFF
            else:
                assert -128 <= d < 128; code[pos] |= d & 0xFF
    return b''.join(struct.pack('>H', x) for x in code) + b''.join(struct.pack('>I', v) for v in lits.values())


def load_hook():
    """0x06026094~0x060260A7(20 B) → mov.l @(2,PC),r3 · jmp @r3 · nop · nop×3 · .long 동굴 · nop×2"""
    return struct.pack('>HHHHHHIHH', 0xD302, 0x432B, 0x0009, 0x0009, 0x0009, 0x0009, 0, 0x0009, 0x0009)


def ip_blob(name_chars, glyph):
    """IP.BIN 뒤쪽에 실을 것: [동굴][작업 칸 32 B][이름 글꼴 n×22 B]. 반환 (blob, {글자: n})"""
    nmap = {c: i for i, c in enumerate(name_chars)}
    cave = NF_RAM
    probe = load_cave(cave, 0, 0)
    scratch = (cave + len(probe) + 3) & ~3
    nf = scratch + 32
    code = load_cave(cave, nf, scratch)
    font = b''.join(glyph(c)[2:24] for c in name_chars)
    blob = code + b'\0' * (scratch - cave - len(code)) + b'\0' * 32 + font
    if NF_RAM + len(blob) > NF_END:
        raise SystemExit('⛔이름 글꼴이 IP 뒤 구역을 넘침 %d > %d' % (len(blob), NF_END - NF_RAM))
    return blob, nmap


def build(cd, base_used, glyph=None):
    """cd = 원본 COMMON.DAT, base_used = {글자: 기본폰트 index}, glyph = 글자→32 B 글리프
    → (COMMON 편집, 1ST_READ 편집, IP 편집 {IP 오프셋: bytes}, 보고)"""
    rs = rows()
    by_off = {o: (jp, ko) for o, jp, ko in rs}
    # 이름 포인터 전수(레코드 구역의 BE32 중 구역 안을 가리키는 것)
    ptrs = []
    for i in range(REC_LO, REC_HI, 4):
        v = struct.unpack_from('>I', cd, i)[0]
        if RAM + REG_LO <= v < RAM + REG_HI: ptrs.append((i, v - RAM))
    targets = sorted({t for _, t in ptrs})
    unk = [hex(t) for t in targets if t not in by_off and cd[t] != 0]
    if unk: raise SystemExit('⛔이름 표에 없는 포인터 대상 %s' % unk)
    for t in targets:                       # 빈 이름(0xCF28 등)은 원문 그대로
        by_off.setdefault(t, ('', ''))
    errs = []
    blobs = {}
    need = sorted({c for t in targets for c in by_off[t][1] if '가' <= c <= '힣' and c not in base_used})
    ip_b, nmap = ip_blob(need, glyph) if need else (b'', {})
    for t in targets:
        jp, ko = by_off[t]
        if not ko:
            blobs[t] = _orig_name(cd, t); continue
        if len(ko) > ITEM_WIDTH: errs.append('화면 폭 %d > %d: %s' % (len(ko), ITEM_WIDTH, ko))
        b = bytearray()
        for c in ko:
            if c in ASCII_OK: b.append(ord(c))
            elif c in base_used:
                idx = base_used[c]; assert idx < 256, (c, idx); b += bytes([0x80, idx])
            elif c in nmap:
                n = NAME_BASE + nmap[c]; assert n < 0x2000; b += bytes([0x80 | (n >> 8), n & 0xFF])
            else: errs.append('글자 없음 %r: %s' % (c, ko))
        blobs[t] = bytes(b) + b'\0'
    if errs: raise SystemExit('⛔아이템 이름:\n  ' + '\n  '.join(errs))
    # 다시 채우기: 같은 문자열은 한 번만(이름이 같은 항목 공유)
    out = bytearray(b'\0' * (REG_HI - REG_LO)); pos = 0; newaddr = {}; seen = {}
    for t in targets:
        bl = blobs[t]
        if bl in seen: newaddr[t] = seen[bl]; continue
        newaddr[t] = REG_LO + pos; seen[bl] = REG_LO + pos
        out[pos:pos + len(bl)] = bl; pos += len(bl)
    cave_off = (REG_LO + pos + 3) & ~3
    cave = cave_code(RAM + cave_off)
    if cave_off + len(cave) > REG_HI: raise SystemExit('⛔이름 구역 넘침(동굴 포함) %d > %d' % (cave_off + len(cave) - REG_LO, REG_HI - REG_LO))
    out[cave_off - REG_LO:cave_off - REG_LO + len(cave)] = cave
    shop_off = (cave_off + len(cave) + 3) & ~3
    shop = shop_wrapper(RAM + shop_off)
    if shop_off + len(shop) > REG_HI: raise SystemExit('⛔이름 구역 넘침(가게 감싸기 포함)')
    out[shop_off - REG_LO:shop_off - REG_LO + len(shop)] = shop
    ce = {REG_LO: bytes(out)}
    for i, t in ptrs: ce[i] = struct.pack('>I', RAM + newaddr[t])
    fe = {HOOK - FR_BASE: hook_code(RAM + cave_off)}
    ipe = {}
    if ip_b:
        lh = bytearray(load_hook()); struct.pack_into('>I', lh, 12, NF_RAM)
        fe[LOAD_HOOK - FR_BASE] = bytes(lh)
        ipe[NF_RAM - IP_RAM] = ip_b
        ipe[0xE0] = struct.pack('>I', NF_RAM - IP_RAM + len(ip_b))      # IP 크기
    rep = '이름 %d개(번역 %d) · 포인터 %d · 구역 %d/%d B · 동굴 0x%08X · 이름 글꼴 %d자(IP %d B)' % (
        len(targets), sum(1 for t in targets if by_off[t][1]), len(ptrs), cave_off + len(cave) - REG_LO, REG_HI - REG_LO,
        RAM + cave_off, len(need), len(ip_b))
    rep += ' · 가게 감싸기 0x%08X' % (RAM + shop_off)
    return ce, fe, ipe, rep, RAM + shop_off


# ■ 가게 목록(TWN_*.PRG)은 이름을 printf(0x060249A6, VDP2 반각 칸 글꼴 직접 쓰기)로 찍는다 → 한글 토큰이 깨짐(2026-11-15 «가게물건깨짐»).
#   가게 이름 호출이 쓰는 리터럴(=printf 주소)을 «감싸기»로 바꾼다:
#     형식 문자열이 정확히 "%s" 면 → printf 커서(0x06052578 x·y, +0x10 팔레트 워드)를 글리프 커서(0x0605258C)로 옮기고
#       메뉴와 같은 변환·출력(0x060255DC)으로 이름을 그린다. 색 = 가게 코드의 짝(팔레트 12→0, 13→1, 14→9)
#     그 밖의 형식("%8d" 등) → 원래 printf 로 그대로 점프(r0·r1 만 씀, 스택·pr 그대로).
PRINTF = 0x060249A6
PCUR = 0x06052578
GCUR = 0x0605258C
CONV = 0x060255DC
TWN_BASE = 0x06054000


def shop_wrapper(addr):
    assert addr % 4 == 0
    code, fix, labels = [], [], {}
    def e(x): code.append(x)
    e(0x61F2)                                   # mov.l @r15,r1   (형식)
    e(0x6014); e(0x8825); fix.append((len(code), 'bf', 'ORIG')); e(0x8B00)     # '%'
    e(0x6014); e(0x8873); fix.append((len(code), 'bf', 'ORIG')); e(0x8B00)     # 's'
    e(0x6010); e(0x8800); fix.append((len(code), 'bt', 'GLYPH')); e(0x8900)    # NUL
    labels['ORIG'] = len(code)
    fix.append((len(code), 'lit0', 'PRINTF')); e(0xD000)                        # mov.l PRINTF,r0
    e(0x402B); e(0x0009)                                                        # jmp @r0
    labels['GLYPH'] = len(code)
    e(0x4F22)                                   # sts.l pr,@-r15
    fix.append((len(code), 'lit3', 'PCUR')); e(0xD300)
    e(0x6432); e(0x5531)                        # r4 = x, r5 = y
    e(0x8538); e(0x600D)                        # r0 = 팔레트 워드(extu)
    e(0x4019); e(0x4009); e(0x4009)             # r0 >>= 12
    e(0xE100)                                   # r1 = 0
    e(0x880D); fix.append((len(code), 'bf', 'N1')); e(0x8B00); e(0xE101)
    labels['N1'] = len(code)
    e(0x880E); fix.append((len(code), 'bf', 'N2')); e(0x8B00); e(0xE109)
    labels['N2'] = len(code)
    fix.append((len(code), 'lit2', 'GCUR')); e(0xD200)
    e(0x2212); e(0x1241); e(0x1252); e(0x1243); e(0x1254)    # @0 색 · @4 x · @8 y · @C x · @10 y
    e(0xE114); e(0x1215); e(0xE102); e(0x1216)               # @14 폭 20 · @18 높이 2
    e(0x54F2)                                   # r4 = 이름(@(8,r15): pr·형식 다음)
    fix.append((len(code), 'lit0', 'CONV')); e(0xD000)
    e(0x400B); e(0x0009)                        # jsr @r0
    e(0x4F26); e(0x000B); e(0x0009)             # lds.l @r15+,pr · rts
    if len(code) % 2: e(0x0009)
    lits = {'PRINTF': PRINTF, 'PCUR': PCUR, 'GCUR': GCUR, 'CONV': CONV}
    lb = addr + 2 * len(code)
    at = {k: lb + 4 * i for i, k in enumerate(lits)}
    for pos, kind, tgt in fix:
        pc = addr + 2 * pos
        if kind.startswith('lit'):
            d = (at[tgt] - ((pc + 4) & ~3)) // 4
            assert 0 <= d < 256 and ((pc + 4) & ~3) + 4 * d == at[tgt]
            code[pos] |= d
        else:
            d = (addr + 2 * labels[tgt] - (pc + 4)) // 2
            assert -128 <= d < 128
            code[pos] |= d & 0xFF
    return b''.join(struct.pack('>H', x) for x in code) + b''.join(struct.pack('>I', v) for v in lits.values())


def shop_sites(b, base=TWN_BASE):
    """가게 모듈에서 «"%s" 형식 + printf» 호출이 쓰는 리터럴 자리(파일 오프셋) 목록"""
    lits = {i for i in range(0, len(b) - 3, 4) if struct.unpack_from('>I', b, i)[0] == PRINTF}
    out = []
    for i in range(0, len(b) - 1, 2):
        w = struct.unpack_from('>H', b, i)[0]
        if w >> 12 != 0xD: continue
        ea = ((base + i + 4) & ~3) + 4 * (w & 0xFF) - base
        if ea not in lits: continue
        fm = False
        for k in range(max(0, i - 30), i + 6, 2):
            ww = struct.unpack_from('>H', b, k)[0]
            if ww >> 12 != 0xD: continue
            e2 = ((base + k + 4) & ~3) + 4 * (ww & 0xFF) - base
            if 0 <= e2 <= len(b) - 4:
                v = struct.unpack_from('>I', b, e2)[0]
                if base <= v < base + len(b) - 3 and b[v - base:v - base + 3] == b'%s\0': fm = True
        if fm: out.append((i, ea))
    return out


def shop_patches(srcdir, wrapper_addr):
    """TWN_*.PRG 의 가게 이름 printf 리터럴 → 감싸기 주소. 반환 {파일: {오프셋: 4 B}}, 보고"""
    import glob
    out, n = {}, 0
    for f in sorted(glob.glob(os.path.join(srcdir, 'TWN_*.PRG'))):
        b = open(f, 'rb').read()
        s = shop_sites(b)
        if not s: continue
        if len(s) != 2: raise SystemExit('⛔가게 이름 호출이 2곳이 아님 %s %s' % (os.path.basename(f), s))
        for _, ea in s:
            assert struct.unpack_from('>I', b, ea)[0] == PRINTF
            out.setdefault(os.path.basename(f), {})[ea] = struct.pack('>I', wrapper_addr)
        n += 1
    return out, '가게 모듈 %d개(리터럴 %d곳)' % (n, sum(len(v) for v in out.values()))


def check_hook_site(fr):
    """1ST_READ 원본의 훅 자리가 예상 바이트인지(다른 판·이미 고친 파일 방지)"""
    o = HOOK - FR_BASE
    if fr[o:o + 10] != HOOK_ORIG:
        raise SystemExit('⛔1ST_READ 훅 자리 바이트가 예상과 다름: %s' % fr[o:o + 10].hex())
    o = LOAD_HOOK - FR_BASE
    if fr[o:o + 20] != LOAD_HOOK_ORIG:
        raise SystemExit('⛔1ST_READ 캐시 적재 훅 자리 바이트가 예상과 다름: %s' % fr[o:o + 20].hex())


def check_ip(ip):
    """원본 IP.BIN: 크기 0x2F00, 이름 글꼴 자리(0x3200~)가 0"""
    sz = struct.unpack_from('>I', ip, 0xE0)[0]
    if sz != 0x2F00 or any(ip[NF_RAM - IP_RAM:NF_END - IP_RAM]):
        raise SystemExit('⛔IP.BIN 이 예상과 다름(크기 0x%X)' % sz)


def make_tsv():
    """items.tsv(off·jp) + work/item_ko.tsv(예전 초안, 빈 항목·특수 문자열 빼고 순서 대응) → items_kr.tsv"""
    it = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'trans', 'items.tsv'), encoding='utf-8')][1:]
    ko = [l.rstrip('\n').split('\t')[-1] for l in open(os.path.join(ROOT, 'work', 'item_ko.tsv'), encoding='utf-8')]
    keep = [r for r in it if r[1] and not r[1].startswith('<')]
    assert len(keep) <= len(ko)
    with open(TSV, 'w', encoding='utf-8', newline='\n') as f:
        f.write('off\tjp\tko\n')
        for r, k in zip(keep, ko):
            f.write('%s\t%s\t%s\n' % (r[0], r[1], k))
    print('items_kr.tsv %d행' % len(keep))


if __name__ == '__main__':
    import sys
    if '--make-tsv' in sys.argv: make_tsv()

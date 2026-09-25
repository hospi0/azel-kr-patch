# -*- coding: utf-8 -*-
"""아주 작은 SH-2 디스어셈블러 — 코드 읽기용(주입 전 판독).

  python tools/sh2dis.py <PRG파일> <시작오프셋16> <길이> [로드주소16]

전부를 덮지 않는다. **리터럴 풀 참조(mov.l @(d,PC))와 분기·호출**을 정확히
풀어 「어느 상수를 어디에 쓰는가」를 보는 게 목적이다.
[[feedback_code_injection_simulate_first]] — 주입은 반드시 시뮬레이션 먼저.
"""
import struct
import sys


def dis(code, off, n, base):
    out = []
    i = off
    end = off + n
    while i < end - 1:
        w = struct.unpack_from('>H', code, i)[0]
        a = base + i
        s = '.word %04X' % w
        nb = (w >> 12) & 0xF
        rn = (w >> 8) & 0xF
        rm = (w >> 4) & 0xF
        d8 = w & 0xFF
        d12 = w & 0xFFF
        if nb == 0xD:                                   # mov.l @(d,PC),Rn
            ea = ((a + 4) & ~3) + d8 * 4
            fo = ea - base
            v = struct.unpack_from('>I', code, fo)[0] if 0 <= fo < len(code) - 3 else 0
            s = 'mov.l @(%02X,PC),R%d   ; [%08X] = %08X' % (d8 * 4, rn, ea, v)
        elif nb == 0x9:                                 # mov.w @(d,PC),Rn
            ea = a + 4 + d8 * 2
            fo = ea - base
            v = struct.unpack_from('>h', code, fo)[0] if 0 <= fo < len(code) - 1 else 0
            s = 'mov.w @(%02X,PC),R%d   ; = %d (0x%X)' % (d8 * 2, rn, v, v & 0xFFFF)
        elif nb == 0xE:
            s = 'mov #%d,R%d' % (struct.unpack('b', bytes([d8]))[0], rn)
        elif nb == 0xA:
            t = d12 - 0x1000 if d12 & 0x800 else d12
            s = 'bra %08X' % (a + 4 + t * 2)
        elif nb == 0xB:
            t = d12 - 0x1000 if d12 & 0x800 else d12
            s = 'bsr %08X' % (a + 4 + t * 2)
        elif nb == 0x8:
            sub = (w >> 8) & 0xF
            t = d8 - 0x100 if d8 & 0x80 else d8
            if sub == 0x9:
                s = 'bt  %08X' % (a + 4 + t * 2)
            elif sub == 0xB:
                s = 'bf  %08X' % (a + 4 + t * 2)
            elif sub == 0xD:
                s = 'bt/s %08X' % (a + 4 + t * 2)
            elif sub == 0xF:
                s = 'bf/s %08X' % (a + 4 + t * 2)
        elif nb == 0x6 and (w & 0xF) == 0x3:
            s = 'mov R%d,R%d' % (rm, rn)
        elif nb == 0x6 and (w & 0xF) == 0x2:
            s = 'mov.l @R%d+,R%d' % (rm, rn)
        elif nb == 0x2 and (w & 0xF) == 0x2:
            s = 'mov.l R%d,@R%d' % (rm, rn)
        elif nb == 0x2 and (w & 0xF) == 0x6:
            s = 'mov.l R%d,@-R%d' % (rm, rn)
        elif nb == 0x6 and (w & 0xF) == 0x0:
            s = 'mov.b @R%d,R%d' % (rm, rn)
        elif nb == 0x1:
            s = 'mov.l R%d,@(%02X,R%d)' % (rm, (w & 0xF) * 4, rn)
        elif nb == 0x5:
            s = 'mov.l @(%02X,R%d),R%d' % ((w & 0xF) * 4, rm, rn)
        elif w == 0x000B:
            s = 'rts'
        elif w == 0x0009:
            s = 'nop'
        elif (w & 0xF0FF) == 0x400B:
            s = 'jsr @R%d' % rn
        elif (w & 0xF0FF) == 0x402B:
            s = 'jmp @R%d' % rn
        elif nb == 0x3 and (w & 0xF) == 0xC:
            s = 'add R%d,R%d' % (rm, rn)
        elif nb == 0x7:
            s = 'add #%d,R%d' % (struct.unpack('b', bytes([d8]))[0], rn)
        out.append('%08X  %04X  %s' % (a, w, s))
        i += 2
    return out


def main():
    code = open(sys.argv[1], 'rb').read()
    off = int(sys.argv[2], 16)
    n = int(sys.argv[3], 16)
    base = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x06006000
    print('\n'.join(dis(code, off, n, base)))


if __name__ == '__main__':
    main()

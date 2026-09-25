# -*- coding: utf-8 -*-
"""세이브스테이트 스냅샷에서 SH-2 레지스터를 뽑는다 (Mednafen 섹션 포맷).

    [32B 섹션이름(널패딩)][4B LE 섹션크기]  그 안에 [1B 이름길이][이름][4B LE 크기][데이터]

★레지스터는 swap16 대상이 아니다 — 그냥 LE u32. swap16 은 Work RAM 쪽만.
[[reference_saturn_state_sh2_regs]]

사용: python dump_regs.py <스냅샷.bin>
"""
import sys, struct

sys.stdout.reconfigure(encoding='utf-8')


def sections(snap):
    """[(이름, 데이터시작, 크기)] — 알려진 섹션 이름을 직접 찾는다."""
    out = []
    for nm in (b'SH2-M', b'SH2-S'):
        i = snap.find(nm)
        while i >= 0:
            # 이름은 32B 널패딩 블록의 시작이어야 한다
            blk = snap[i:i + 32]
            if blk[len(nm)] == 0:
                size = struct.unpack_from('<I', snap, i + 32)[0]
                if 0 < size < len(snap):
                    out.append((nm.decode(), i + 36, size))
                    break
            i = snap.find(nm, i + 1)
    return out


def variables(snap, off, size):
    res, pos, end = {}, off, off + size
    while pos < end:
        nl = snap[pos]
        if nl == 0 or pos + 1 + nl + 4 > end:
            break
        name = snap[pos + 1:pos + 1 + nl].decode('ascii', 'replace')
        pos += 1 + nl
        vsz = struct.unpack_from('<I', snap, pos)[0]
        pos += 4
        res[name] = snap[pos:pos + vsz]
        pos += vsz
    return res


def main():
    snap = open(sys.argv[1], 'rb').read()
    for name, off, size in sections(snap):
        v = variables(snap, off, size)
        print(f'=== {name}  (0x{off:X}, {size}B, 변수 {len(v)}개)')
        pc = struct.unpack('<I', v['PC'])[0] if 'PC' in v else None
        regs = struct.unpack('<16I', v['R']) if 'R' in v and len(v['R']) >= 64 else None
        ctrl = struct.unpack('<3I', v['CtrlRegs'][:12]) if 'CtrlRegs' in v else None
        sysr = struct.unpack('<3I', v['SysRegs'][:12]) if 'SysRegs' in v else None
        if pc is not None:
            print(f'   PC  = {pc:08X}')
        if sysr:
            print(f'   PR  = {sysr[2]:08X}   MACH={sysr[0]:08X} MACL={sysr[1]:08X}')
        if ctrl:
            print(f'   SR  = {ctrl[0]:08X}   GBR ={ctrl[1]:08X} VBR ={ctrl[2]:08X}')
        if regs:
            for i in range(0, 16, 4):
                print('   ' + '  '.join('R%-2d=%08X' % (i + k, regs[i + k]) for k in range(4)))
        for k in ('PC_IF', 'PC_ID'):
            if k in v and len(v[k]) >= 4:
                print(f'   {k}= {struct.unpack("<I", v[k][:4])[0]:08X}')


if __name__ == '__main__':
    main()

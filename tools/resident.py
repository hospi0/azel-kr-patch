# -*- coding: utf-8 -*-
"""세이브스테이트 스냅샷에서 «그 순간 메모리에 올라와 있는 파일»을 찾는다.

Mednafen 섹션(`MAIN`)의 변수 `WorkRAML`/`WorkRAMH` 를 **정식 파싱**해서 꺼낸다.
⛔`MAIN` 태그 위치 + 고정 오프셋으로 잡던 방식은 스테이트 판에 따라 어긋난다
  (2026-08-14 Terra·Azel 둘 다 1바이트씩 밀려 크립 대조가 실패했다).
Work RAM 은 **swap16** 상태로 저장된다.

사용: python resident.py <스냅샷> <디스크Track1>
"""
import sys, os, struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from iso9660 import Iso
from dump_regs import variables


def workram(snap):
    m = snap.find(b'MAIN')
    size = struct.unpack_from('<I', snap, m + 32)[0]
    v = variables(snap, m + 36, size)

    def sw(b):
        a = bytearray(b)
        a[0::2], a[1::2] = b[1::2], b[0::2]
        return bytes(a)
    return sw(v['WorkRAML']), sw(v['WorkRAMH'])


def main():
    snap = open(sys.argv[1], 'rb').read()
    lo, hi = workram(snap)
    iso = Iso(sys.argv[2])
    out = []
    for path, lba, sz in iso.walk():
        n = path.split('/')[-1]
        if sz < 128 or path.endswith('/'):
            continue
        crib = iso.read(lba, sz)[:96]
        i = hi.find(crib)
        if i >= 0:
            out.append((0x06000000 + i, 'HWRAM', n, sz))
            continue
        j = lo.find(crib)
        if j >= 0:
            out.append((0x00200000 + j, 'LWRAM', n, sz))
    for a, w, n, sz in sorted(out):
        print('%08X  %-5s %-16s %d B' % (a, w, n, sz))
    print('상주 %d개' % len(out))


if __name__ == '__main__':
    main()

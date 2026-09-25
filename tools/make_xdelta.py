# -*- coding: utf-8 -*-
"""배포용 xdelta 패치 4장 — 프로젝트 루트에 만든다.

  python tools/make_xdelta.py

원본(무수정, F드라이브 **안쪽 중첩 폴더**) ↔ 패치본(바깥) 을 견주어
`azel_kr_disc{1,2,3,4}.xdelta` 를 만든다.

★크기가 바뀌지 않는 패치라, 사용자가 실수로 두 번 적용해도 xdelta 가
  원본 해시로 거른다. Track 2·3(오디오)은 손대지 않으므로 패치 대상이 아니다.
"""
import os
import subprocess
import sys

VERSION = '0.9'          # 파일명 = azel_kr_<VERSION>_disc<N>.xdelta
XDELTA = r'C:\claude\utils\xdelta.exe'
ROOT = r'F:\hospi\roms\ss roms\azel'
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DISCS = [
    (1, r'Azel - Panzer Dragoon RPG (Japan) (Disc 1) (2M)',
     r'Azel - Panzer Dragoon RPG (Japan) (Disc 1) (2M) (Track 1).bin'),
    (2, r'Azel - Panzer Dragoon RPG (Japan) (Disc 2) (2M)',
     r'Azel - Panzer Dragoon RPG (Japan) (Disc 2) (2M) (Track 1).bin'),
    (3, r'Azel - Panzer Dragoon RPG (Japan) (Disc 3) (2M)',
     r'Azel - Panzer Dragoon RPG (Japan) (Disc 3) (2M) (Track 1).bin'),
    (4, r'Azel - Panzer Dragoon RPG (Japan) (Disc 4) (2M, 3M)',
     r'Azel - Panzer Dragoon RPG (Japan) (Disc 4) (2M, 3M) (Track 1).bin'),
]


def main():
    if not os.path.exists(XDELTA):
        raise SystemExit('xdelta 가 없다: %s' % XDELTA)
    for n, folder, track in DISCS:
        src = os.path.join(ROOT, folder, track)     # 무수정 원본(중첩 폴더)
        dst = os.path.join(ROOT, track)             # 패치본(바깥)
        out = os.path.join(OUT, 'azel_kr_%s_disc%d.xdelta' % (VERSION, n))
        for p in (src, dst):
            if not os.path.exists(p):
                print('★없음: %s' % p)
                break
        else:
            if os.path.getsize(src) != os.path.getsize(dst):
                print('★크기가 다르다 — 원본/패치본이 뒤바뀌었을 수 있다: D%d' % n)
                continue
            if os.path.exists(out):
                os.remove(out)
            r = subprocess.run([XDELTA, '-e', '-9', '-s', src, dst, out],
                               capture_output=True)
            if r.returncode != 0:
                print('★xdelta 실패 D%d: %s' % (n, r.stderr.decode('utf-8', 'replace')[:200]))
                continue
            print('D%d → %s  %d B' % (n, os.path.basename(out),
                                      os.path.getsize(out)))


if __name__ == '__main__':
    main()

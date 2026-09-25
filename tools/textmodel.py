# -*- coding: utf-8 -*-
"""Azel 텍스트 모델 — 글리프 인덱스 스트림.

확정된 구조(디스크1 관측):
  * 글리프 공간은 두 층이다.
      index 0..255   : 상주 기본 폰트 = COMMON.DAT +0x1068A 의 256글리프
                       (숫자·히라가나·가타카나·구두점·A~Z·상용한자 일부)
      index 256..    : 장면별 `.FNT` 서브셋 = FNT[index-256]  (한자, 첫등장 순서)
    근거: 텍스트 안 index>=256 의 첫등장 순번이 256부터 완전한 오름차순.
  * 토큰
      byte >= 0x80 : 2바이트 글자 토큰, index = ((b & 0x7F) << 8) | next
      byte <  0x80 : 1바이트 제어코드   (관측: 0x00 종료/구분, 0x06 개행)
"""
BASE_OFF = 0x1068A
BASE_N = 256


def base_glyphs(common_dat):
    return [common_dat[BASE_OFF + i * 32: BASE_OFF + (i + 1) * 32] for i in range(BASE_N)]


def decode(data, off, end, nscene, max_ctrl=0x10):
    """off..end 를 토큰열로 읽는다 → ([('g',idx)|('c',code)], 멈춘 오프셋)."""
    out = []
    i = off
    while i < end:
        b = data[i]
        if b >= 0x80:
            if i + 1 >= end:
                break
            idx = ((b & 0x7F) << 8) | data[i + 1]
            if idx >= BASE_N + nscene:
                break
            out.append(('g', idx))
            i += 2
        else:
            if b > max_ctrl:
                break
            out.append(('c', b))
            i += 1
    return out, i


def find_regions(data, nscene, minlen=48):
    """파일 전체에서 토큰열로 해석되는 구간을 긁는다 (모집단 하한 측정용)."""
    regions = []
    i = 0
    n = len(data)
    while i < n:
        toks, e = decode(data, i, n, nscene)
        if e - i >= minlen and any(k == 'g' for k, _ in toks):
            regions.append((i, e, toks))
            i = e
        else:
            i += 1
    return regions

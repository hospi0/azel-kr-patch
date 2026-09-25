# -*- coding: utf-8 -*-
"""Azel/PDS 문자열 테이블 파서 — JP·US 공용.

디스크1 실측으로 확정된 구조:
  * 텍스트는 `.PRG` 안에 **널 종단 문자열이 연속 배치**된 테이블로 들어 있다.
  * 한 문자열 안에서 바이트는 세 종류다.
        b >= 0x80        2바이트 글리프 토큰. index = ((b & 0x7F) << 8) | next
                         index 0..255 = COMMON.DAT 상주 기본 폰트
                         index 256..  = 그 모듈 짝 `.FNT` 의 index-256
        0x20 <= b < 0x80 **1바이트 글리프 토큰. index = b 그대로** (ASCII 아님)
        b < 0x20         1바이트 제어코드 (0x00 = 문자열 종단)
  * ★1바이트 토큰이 ASCII가 아니라는 근거(디스크1 `TWN_ZOAH.PRG` 실측):
        0xC663 `3C`      → ASCII '<'  vs 글리프 60 ')'      ← 앞 문장의 닫는 괄호
        0xC8E5 `20 …`    → ASCII ' いな)' vs 글리프 'ないな)'
        0xE7C0 `23`      → ASCII '#'  vs 글리프 35 'ね'
        0xF0F3 `3A`      → ASCII ':'  vs 글리프 58 '…'
    네 곳 모두 글리프 해석만 말이 된다. 기본 폰트 배열이 あいうえお순이라
    index >= 0x20 인 글자(な~ン)만 1바이트로 쓸 수 있고, 그래서 사용 빈도가 낮다.
  * 대사 사이사이에 `T_SF_016.PCM` 같은 **음성 파일명 문자열이 인터리브**돼 있다.
    이건 렌더 대상이 아니라 파일명 인수이므로 진짜 ASCII다. 소비자가 다르다.
    JP·US 모두 같은 자리·같은 순서라 대응 정렬의 앵커로 쓸 수 있다.

JP와 US는 같은 테이블을 같은 순서로 갖는다(오프셋만 다르다).
US판은 같은 1바이트 토큰을 영문 글리프로 렌더한다(폰트가 다르다 — 위치 미확정).
"""
import re

# ★확장자를 열거하면 빠진 게 반드시 나온다 — `ENCAM.BDB` 가 「대사」로 새어
#   들어왔다. 파일명 «꼴»로 판정한다(진짜 대사는 전각 가나라 이 꼴이 안 된다).
PCM_RE = re.compile(rb'^[A-Z0-9_]+\.[A-Z][A-Z0-9]{1,3}$')


def parse_table(data, start, nmax=0x8000, lenient=False, max_bad=8):
    """start 부터 널 종단 문자열을 연속으로 읽는다.

    반환 [(offset, raw, tokens)], 끝 오프셋.
    tokens = [('g', idx) | ('a', ch) | ('c', code) | ('x', byte)]

    'x' = 글리프 인덱스 범위(nmax)를 넘는 리드 바이트. 미해독 제어코드로 보인다.
    lenient=False 면 거기서 멈추고, True 면 1바이트 소비하고 계속 읽는다.
    한 문자열 안에서 'x' 가 max_bad 개를 넘으면 테이블이 끝난 것으로 보고 멈춘다.
    """
    out = []
    i = start
    n = len(data)
    while i < n:
        j = i
        toks = []
        bad = 0
        ok = True
        while j < n:
            b = data[j]
            if b == 0x00:
                j += 1
                break
            if b >= 0x80:
                if j + 1 >= n:
                    ok = False
                    break
                idx = ((b & 0x7F) << 8) | data[j + 1]
                if idx >= nmax:
                    if not lenient:
                        ok = False
                        break
                    toks.append(('x', b))
                    bad += 1
                    if bad > max_bad:
                        ok = False
                        break
                    j += 1
                    continue
                toks.append(('g', idx))
                j += 2
            elif b >= 0x20:
                toks.append(('g1', b))
                j += 1
            else:
                toks.append(('c', b))
                j += 1
        else:
            ok = False
        if not ok:
            break
        out.append((i, data[i:j - 1], toks))
        i = j
    return out, i


def is_asset_name(raw):
    return bool(PCM_RE.match(raw))


def kind(raw, toks):
    """문자열 갈래 — 'asset'(파일명, 진짜 ASCII) | 'glyph'(대사) | 'ctrl' | 'empty'"""
    if not toks:
        return 'empty'
    if is_asset_name(raw):
        return 'asset'
    if any(k in ('g', 'g1') for k, _ in toks):
        return 'glyph'
    return 'ctrl'

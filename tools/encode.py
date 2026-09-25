# -*- coding: utf-8 -*-
"""번역문 → 글리프 인덱스 스트림.

문법(§7.3, §7.7):
    index < 0x80        1바이트 토큰 (그대로)
    index >= 0x80       2바이트 토큰 `0x80|(idx>>8)`, `idx&0xFF`
    제어코드            `<XX>` 표기 → 그 1바이트, `\\n` → 0x06
    문자열 끝           0x00

★**원문 길이를 정확히 맞춘다.** 이 게임은 문자열별 포인터가 없고 순차 소비로
  보이므로(§7.13), 번역문이 짧아 남는 자리를 그냥 두면 **빈 문자열이 하나 더 생겨
  그 뒤 대사가 통째로 밀린다**. 남으면 «공백 글리프»로 채운다.
  길면 당연히 다음 문자열을 침범하므로 금지.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import basemap

_REVERSE_KEEP = basemap.REVERSE_KEEP

PAD_1B = None      # 1바이트 공백 글리프 index (alloc 이 예약)
PAD_2B = 1         # 기본 폰트의 빈 글리프 = 공백

# `<!XX>` = 파서가 글리프로 못 읽은 생바이트(index 가 7000 이상으로 나온다 —
# 글리프일 수 없다). 정체는 미상이지만 **그대로 내보내야** 원본이 보존된다.
# 이 표기를 모르면 `<`,`!`,`D`,`B`,`>` 다섯 글자로 인코딩해 원본을 깨뜨린다.
TOKEN = re.compile(r'<!([0-9A-F]{2})>|<([0-9A-F]{2})>|\\n|(.)', re.S)


class Budget(Exception):
    pass


def encode(text, cmap, budget=None, pad=True, allow1b=True, pad_center=False,
           keep2b=False):
    """cmap: {글자: index}. 반환 bytes(종단 포함).

    ★`allow1b=False` 면 글자를 **전부 2바이트 토큰**으로 쓴다.
      원본이 1바이트 토큰을 한 번도 안 쓴 문자열에는 1바이트를 넣으면 안 된다 —
      그런 자리를 그리는 렌더러는 **글자당 2바이트를 무조건 읽어서**, 1바이트가
      섞이면 그 뒤가 통째로 어긋난다(실기: 「호밍 레이저」 뒤에 `이이이…스공줌`
      이 줄줄이 붙었고, 번역이 짧을수록 쓰레기가 길어졌다).
    """
    # ★★2026-08-14: 1바이트 토큰을 «쓸 수 있으면 무조건» 쓰던 것을 고쳤다.
    #   1바이트로 줄여봐야 남는 자리는 어차피 «공백 글리프»로 메워지므로, 예산이
    #   넉넉한 문자열에서는 화면에 **쓸데없는 빈 칸이 붙는다**(실기 제보: 전투 기술명
    #   「기생충」 뒤에 공백 한 칸. 원본 `寄生虫`=2바이트×3+종단=7B 인데 번역을
    #   1바이트로 줄여 5B 로 만들고 공백 2B 를 덧붙이고 있었다).
    #   ⇒ **전부 2바이트로 써서 예산에 들어가면 그쪽을 쓴다**(패딩 최소).
    #     안 들어갈 때만 종전대로 1바이트 토큰으로 줄인다.
    #   ⛔allow1b=False 인 모듈(BTL_T0 류)은 애초에 2바이트뿐이라 영향 없음.
    #   ⚠2026-08-15: 이 정책이 6,389곳의 바이트를 바꾼다. 원인 절개용으로
    #     `AZEL_PAD_MIN=0` 을 주면 예전(1바이트 우선) 동작으로 되돌아간다.
    import os as _os
    if allow1b and budget is not None and _os.environ.get('AZEL_PAD_MIN') != '0':
        two = encode(text, cmap, budget=None, pad=False, allow1b=False,
                     keep2b=keep2b)
        if len(two) <= budget:
            allow1b = False

    out = bytearray()
    tail = 0                # 끝에 붙은 «제어코드·생바이트» 런의 길이
    head = 0                # 앞에 붙은 «제어코드·유지글자» 런의 길이
    in_head = True
    for m in TOKEN.finditer(text):
        raw, ctrl, ch = m.group(1), m.group(2), m.group(3)
        if raw is not None:                 # `<!XX>` 생바이트 — 그대로
            out.append(int(raw, 16))
            tail += 1
            if in_head:
                head += 1
            continue
        if ctrl is not None:
            out.append(int(ctrl, 16))
            tail += 1
            if in_head:
                head += 1
            continue
        if ch is None:                      # '\n'
            out.append(0x06)
            tail += 1
            continue
        tail = 0                            # 글자가 나오면 꼬리 런이 끊긴다
        idx = cmap.get(ch)
        if idx is None:
            raise Budget('슬롯에 없는 글자: %r (%s)' % (ch, text[:20]))
        # ★1바이트로 쓸 수 있는 건 **0x20~0x7F 뿐**이다.
        #   index 0x00~0x1F 는 1바이트로 쓰면 제어코드가 되므로 반드시 2바이트로.
        # ★★2026-08-15: «원문이 그대로 유지하는 글자»(`)` `숫자` `기호` 등,
        #   basemap.REVERSE_KEEP)는 **원문이 쓰던 폭을 그대로 따라야 한다.**
        #   allow1b=False 로 2바이트로 바꿨더니 `)`(원본 1바이트 `3C`)가
        #   `80 3C` 가 되어 뒤가 한 바이트씩 밀렸고, 예산이 모자라 패딩까지
        #   끼면서 지명 상자가 깨졌다(실기: 「카라반」→「가·깨짐·라·반」).
        #   ⇒ KEEP 글자는 allow1b 와 무관하게 1바이트 구간이면 1바이트로 쓴다.
        #   ★★2026-08-15 실측: 원본이 KEEP 글자를 «2바이트»로 쓴 자리가 6,797곳,
        #     1바이트로 쓴 자리는 454곳뿐이다. 그래도 기본값을 1바이트로 두는 건
        #     **1바이트가 예산을 벌어주기 때문**이다 — 「원본 폭 그대로」를 전면
        #     적용하면 2,659곳이 예산 초과로 터진다. 그래서 폭이 어긋나 실제로
        #     구조가 깨진 자리만 `keep2b=True` 로 자리 지정해 되돌린다
        #     (build_kr.KEEP_2BYTE_PLACES).
        #   ★`keep2b` 라도 **선두 런 안의 KEEP 은 1바이트**로 둔다 — 원본이
        #     그렇다(TWN_EXCA 0x18B7 은 머리 `)` 만 `3c`(1B)이고, 뒤의
        #     `(` `…` `)` 는 전부 2바이트다).
        keep = _REVERSE_KEEP.get(ch)
        if keep is not None and 0x20 <= keep < 0x80 and keep2b and not in_head:
            out += bytes([0x80 | (keep >> 8), keep & 0xFF])
            in_head = False
        elif keep is not None and 0x20 <= keep < 0x80:
            out.append(keep)
            if in_head:
                head += 1
        elif allow1b and 0x20 <= idx < 0x80:
            out.append(idx)
            in_head = False
        else:
            out += bytes([0x80 | (idx >> 8), idx & 0xFF])
            in_head = False
    out.append(0x00)

    if budget is None:
        return bytes(out)
    if len(out) > budget:
        raise Budget('예산 초과 %d > %d : %s' % (len(out), budget, text[:24]))
    if pad and len(out) < budget:
        gap = budget - len(out)
        pad_bytes = bytearray()
        # 종단 앞에 공백을 채운다. 홀수 자리는 1바이트 공백이 있어야 메운다.
        # ★★2026-08-15: 1바이트 공백을 **맨 뒤에** 놓는다. 앞에 두면
        #   `pad_center` 가 패딩을 반으로 자를 때 **2바이트 토큰 한가운데가
        #   갈린다**(실측: `7f 80 01 80 | 01 80 01 …` — 그 뒤가 통째로 어긋나
        #   TWN_CARA 0xB007 의 제어코드 구조가 깨졌다).
        #   앞쪽을 전부 2바이트 토큰으로 채워두면 짝수 지점에서 잘라도 안전하다.
        odd = gap % 2
        if odd:
            if PAD_1B is None:
                raise Budget('1바이트가 남는데 1바이트 공백 글리프가 없다: %s'
                             % text[:24])
            gap -= 1
        while gap >= 2:
            pad_bytes += bytes([0x80 | (PAD_2B >> 8), PAD_2B & 0xFF])
            gap -= 2
        if odd:
            pad_bytes.append(PAD_1B)
        # ★★패딩은 «끝에 붙은 제어코드 앞»에 넣는다 — 종단 바로 앞이 아니다.
        #   원본이 `… 03 00`(닫는 제어코드 다음이 곧바로 종단자)인데 우리가
        #   `… 03 [공백들] 00` 으로 만들면, 그 제어코드가 **인수를 먹는 종류**일 때
        #   패딩이 인수로 빨려 들어가 화면에 쓰레기가 붙는다.
        #   실기(BTL_T0 전투 튜토리얼): 「호밍 레이저」 뒤에 `이이`+플레이어 이름이
        #   따라붙었다. 원본에는 그 자리에 아무것도 없다.
        cut = len(out) - 1 - tail           # 종단자·꼬리 제어코드 앞
        if pad_center and len(pad_bytes) >= 4:
            # ★★2026-08-15: 지명 상자는 «토큰 수»만큼 칸을 잡고 가운데 정렬한다.
            #   패딩을 전부 뒤에 몰면 글자가 왼쪽으로 쏠려 오른쪽이 휑하다
            #   (실기: 「카라반」 뒤로 두 칸이 비었다). 앞뒤로 나눠 넣는다.
            #   ★앞 패딩은 «선두 제어코드·유지글자 런 뒤»에 넣어야 한다 —
            #     이 자리 원문은 `)`+제어코드로 시작하는데(`3c 1d 1a 01`),
            #     그 앞에 넣으면 머리표가 깨진다.
            # ★2바이트 토큰 경계에서만 자른다 — 꼬리의 1바이트 공백은 제외하고
            #   앞쪽 2바이트 구간 안에서 짝수 지점을 고른다.
            two_n = len(pad_bytes) - (1 if odd else 0)
            half = (two_n // 2) & ~1
            out = (out[:head] + pad_bytes[:half] + out[head:cut]
                   + pad_bytes[half:] + out[cut:])
        else:
            out = out[:cut] + pad_bytes + out[cut:]
    return bytes(out)


def decode_len(raw):
    """원문 바이트열의 길이(종단 포함) — 예산 계산용."""
    return len(raw) + 1

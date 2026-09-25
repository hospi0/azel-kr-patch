# -*- coding: utf-8 -*-
"""반각(JIS X0201) 이름표 코덱 — 아이템 이름이 여기 산다.

★★이 표는 **글리프 인덱스 스트림이 아니다.** 반각 1바이트 코드로 저장돼 있고
  렌더러가 **코드에 박힌 구간별 상수**로 글리프 index 를 만든다(데이터 표가 아님).

      0x30~0x39 숫자   → index 2~11        (byte - 46)
      0x41~0x5A 영문   → index 190~215     (byte + 125)
      0xA1~0xDF 반각가나 → index 67~129     (byte - 0x5E)

  그래서 «이름에 쓸 수 있는 글리프는 99칸뿐»이다. 한글을 넣으려면 그 99칸에
  한글을 굽고 이름을 그 코드로 써야 한다. 서로 다른 음절 99개가 상한이다.

  ⚠탁점: `ﾞ`(0xDE)·`ﾟ`(0xDF)는 앞 글자와 합쳐져 «탁점 글리프»가 된다
  (`ﾌ`+`ﾟ` → プ). 한글로 쓸 때는 이 두 코드를 쓰지 않는다.
"""
import sys

# 반각 코드 0xA1 부터의 글자(참고용 — 사람이 읽으려고 둔다)
HALF = ('｡｢｣､･ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ'
        'ﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ')
HALF_BASE = 0xA1

KANA_LO, KANA_HI = 0xA1, 0xDF          # → index 67..129
DAKUTEN = (0xDE, 0xDF)


def to_index(b):
    """반각 코드 → 글리프 index (모르면 None)."""
    if 0x30 <= b <= 0x39:
        return b - 46
    if 0x41 <= b <= 0x5A:
        return b + 125
    if KANA_LO <= b <= KANA_HI:
        return b - 0x5E
    return None


def from_index(i):
    """글리프 index → 반각 코드 (못 쓰면 None)."""
    if 2 <= i <= 11:
        return i + 46
    if 190 <= i <= 215:
        return i - 125
    if 67 <= i <= 129:
        return i + 0x5E
    return None


def usable_indices():
    """이름표가 가리킬 수 있는 글리프 index 전부."""
    return ([i for i in range(2, 12)] + [i for i in range(190, 216)] +
            [i for i in range(67, 130)])


def read_name(data, off, limit=40):
    """반각 문자열 하나 읽기 → (사람이 읽는 글자열, 다음 오프셋)."""
    out = []
    j = off
    while j < len(data) and j < off + limit:
        b = data[j]
        if b == 0:
            return ''.join(out), j + 1
        if 0x20 <= b < 0x7F:
            out.append(chr(b))
        elif HALF_BASE <= b <= 0xDF:
            out.append(HALF[b - HALF_BASE])
        else:
            return None, j
        j += 1
    return None, j

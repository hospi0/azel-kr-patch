# -*- coding: utf-8 -*-
"""번역문이 **화면 박스 안에 다 들어가는가**를 전수로 막는다 (2026-08-15).

경위: 도감·읽을거리에서 번역이 박스를 넘쳐 아래가 잘렸다. 되읽기 검증도,
제어코드 검증도 이걸 못 잡는다 — 바이트는 멀쩡하기 때문이다. 개별 자리를
땜빵으로 고쳐봐야 **다른 자리가 터졌는지 알 방법이 없어서** 검사기를 둔다.

판정
    창 = (모듈, 폭).  폭 = 그 단위 원문의 **최대 줄 길이**(칸).
    한계 줄 수 = 실기 스샷으로 잰 값(MEASURED)이 있으면 그것,
                 없으면 **그 창의 원문이 실제로 쓰는 최대 줄 수**.
    검사 = 엔진처럼 «문자 단위»로 접었을 때의 줄 수 ≤ 한계.

★한계를 원문 «줄 수»로 두면 안 된다 — 원문은 줄마다 폭에 딱 맞게 손으로 접혀
  있어서 접기 전후가 같지만, 우리 번역은 폭을 넘으면 엔진이 한 번 더 접는다.
★★창마다 다르다. 폭만으로 묶으면 안 된다(같은 폭 17이라도 MENUBK 읽을거리는
  7줄, 다른 창은 더 길다). 모듈까지 함께 봐야 한다.

실측값(실기 스샷)
    MENUBK 폭17 «읽을거리» = 7줄   — 「아직 문명의 빛을 모르는 변경의」가 17칸
    MENUEN 폭12 «도감»     = 10줄

사용: python verify_fit.py   (실패하면 종료코드 1)
"""
import os, sys, csv, collections, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

NL = chr(92) + 'n'
TOK = re.compile(r'<!?[0-9A-Fa-f]{2}>|(.)', re.S)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 실기 스샷으로 잰 «박스 한계 줄 수». 추측 금지 — 잰 것만 적는다.
MEASURED = {
    ('MENUBK', 17): 7,
    ('MENUEN', 12): 10,
}


def cells(s):
    return sum(1 for m in TOK.finditer(s) if m.group(1))


def wrapped(text, width):
    """엔진처럼 «문자 단위»로 접었을 때의 줄 수."""
    n = 0
    for seg in text.split(NL):
        c = cells(seg)
        n += max(1, -(-c // width))
    return n


def load():
    ko = {}
    with open(os.path.join(REPO, 'work/trans/ko.tsv'), encoding='utf-8') as f:
        for line in f:
            jp, sep, k = line.rstrip('\n').partition('\t')
            if sep:
                ko[jp] = k
    units = list(csv.DictReader(
        open(os.path.join(REPO, 'work/trans/units.tsv'), encoding='utf-8'),
        delimiter='\t'))
    mods = {}
    for r in csv.DictReader(
            open(os.path.join(REPO, 'work/trans/places.tsv'), encoding='utf-8'),
            delimiter='\t'):
        mods.setdefault(r['id'], set()).add(r['module'])
    return ko, units, mods


def caps(units, mods):
    cap = collections.defaultdict(int)
    for u in units:
        jp = u['jp']
        if NL not in jp:
            continue
        w = max(cells(x) for x in jp.split(NL))
        if w < 4:
            continue
        for m in mods.get(u['id'], ()):
            cap[(m, w)] = max(cap[(m, w)], wrapped(jp, w))
    cap.update(MEASURED)
    return cap


def main():
    ko, units, mods = load()
    cap = caps(units, mods)
    bad = []
    wideb = []
    checked = 0
    for u in units:
        jp = u['jp']
        k = ko.get(jp, '')
        if NL not in jp or not k or k == jp:
            continue
        w = max(cells(x) for x in jp.split(NL))
        if w < 4:
            continue
        ms = sorted(mods.get(u['id'], ()))
        if not ms:
            continue
        c = min(cap[(m, w)] for m in ms)
        if not c:
            continue
        checked += 1
        n = wrapped(k, w)
        # ★★두 가지를 다 봐야 한다.
        #   ① 접은 뒤 «줄 수» ≤ 박스 한계        (아래가 잘린다)
        #   ② **줄 하나하나가 폭 이하**          (넘으면 엔진이 낱말 한가운데서
        #      접어 「덤벼」 「리다.」 같은 조각 줄이 생긴다 — 실기 도감에서 확인)
        wide = max(cells(x) for x in k.split(NL))
        if n > c:
            bad.append((n - c, ms[0], w, c, n, u['id'], k))
        elif wide > w:
            wideb.append((wide - w, ms[0], w, wide, u['id'], k))
    bad.sort(reverse=True)
    print('검사 %d단위 / 창 %d개' % (checked, len(cap)))
    print('박스를 넘치는 번역: %d개 %s' % (len(bad), '✅' if not bad else '❌'))
    for d, m, w, c, n, uid, k in bad[:30]:
        print('   +%d줄  %-10s 폭%-3d 한계%-3d → %d줄  id=%-6s %s'
              % (d, m, w, c, n, uid, k[:40].replace(NL, '/')))
    if len(bad) > 30:
        print('   … 외 %d개' % (len(bad) - 30))
    print('줄이 창 폭을 넘는 번역: %d개 %s'
          % (len(wideb), '✅' if not wideb else '❌'))
    for d, m, w, wd, uid, k in wideb[:20]:
        print('   +%d칸  %-10s 폭%-3d → %d칸  id=%-6s %s'
              % (d, m, w, wd, uid, k[:40].replace(NL, '/')))
    if len(wideb) > 20:
        print('   … 외 %d개' % (len(wideb) - 20))
    return 1 if (bad or wideb) else 0


if __name__ == '__main__':
    sys.exit(main())

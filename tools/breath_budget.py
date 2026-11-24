# 숨 예산 집계 (7.6, docs/숨예산.md 8.3). F6·F8·보스전이 data/breath_budget.json에 남긴 기록을 세 표로 보여 준다
# 실행: python tools/breath_budget.py [기록 파일]   (기본 config.BREATH_BUDGET_PATH)
# 1. 탐험 용량표 (숨예산 3장)  2. 구간표 (7.6 목표 1·2, 숨예산 3.4)  3. 보스표 (숨예산 5.4·5.5)
# 경로 계산·이동 모델은 만들지 않는다 (7.6). 비율은 기록의 used를 지금 config 용량으로 다시 나눠 낸다
# (용량을 바꾼 뒤 다시 돌리면 예전 기록이 새 용량 기준으로 다시 보인다)

import json
import os
import sys
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, ROOT)
import config  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')   # cp949 콘솔에서도 한글 (18장 57번)

ROOM_DIR = os.path.join(ROOT, 'data', 'rooms')
SCOPE_REGIONS = config.SCOPE_REGIONS[config.SCOPE]
SCOPE_BOSSES = dict(minimum={'borer', 'moss_warden'},
                    target={'borer', 'moss_warden', 'archsage', 'colossus', 'king'})


def load_records(path):
    records = []
    with open(path, encoding='utf-8') as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                print(f'[건너뜀] {n}번째 줄: JSON 아님')
                continue
            r.setdefault('type', 'segment')   # type이 없는 예전 F6 줄 (숨예산 8.1)
            records.append(r)
    return records


def load_rooms():
    # 방 id → (구역, 화면 수, 보스방?, 게이트방?)
    rooms = {}
    for folder, _, files in os.walk(ROOM_DIR):
        for name in files:
            if name.endswith('.json'):
                with open(os.path.join(folder, name), encoding='utf-8') as f:
                    d = json.load(f)
                w, h = d.get('size', [1, 1])
                rooms[name[:-5]] = (d.get('region'), w * h, bool(d.get('boss')), bool(d.get('breath_gates')))
    return rooms


def room_of(gid):
    return (gid or '').split(':')[0]


def cap(lv):
    return config.BREATH_CAPACITY[lv]


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def table(headers, rows):
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h))
              for i, h in enumerate(headers)]
    print('  '.join(str(h).ljust(w) for h, w in zip(headers, widths)))
    print('  '.join('-' * w for w in widths))
    for r in rows:
        print('  '.join(str(c).ljust(w) for c, w in zip(r, widths)))


# ---------- 1. 탐험 용량 (숨예산 3장) ----------

def explore_table(records, rooms):
    print('\n=== 1. 탐험 용량표 (기준 Lv 숨 하나로 탐험 대상 화면의 '
          f'{config.BREATH_EXPLORE_RATIO[0]:.0%}~{config.BREATH_EXPLORE_RATIO[1]:.0%}) ===')
    lo, hi = config.BREATH_EXPLORE_RATIO
    totals = defaultdict(int)
    for region, screens, boss, gate in rooms.values():
        if not boss and not gate:
            totals[region] += screens
    by_region = defaultdict(list)
    skipped = 0
    for r in records:
        if r['type'] != 'explore' or r.get('void'):
            continue
        if r['breath_lv'] != config.BREATH_REF_LEVEL.get(r['region']):
            skipped += 1   # 기준 레벨이 아닌 측정은 용량을 정하는 데 쓰지 않는다 (3.2 1번)
            continue
        by_region[r['region']].append(r)
    rows = []
    want = {}   # 레벨 → [(구역, 제안 용량)]
    for region in SCOPE_REGIONS:
        lv = config.BREATH_REF_LEVEL.get(region)
        if lv is None:
            continue
        runs = by_region.get(region, [])
        total = totals.get(region, 0)
        if not runs:
            rows.append((region, lv, cap(lv), total, 0, '-', '-', '측정 없음'))
            continue
        # 화면 수는 지금 방 JSON으로 다시 센다 (방 크기를 바꿨을 수 있다)
        ratios = [sum(rooms[x][1] for x in r['rooms'] if x in rooms) / total for r in runs] if total else [0]
        avg = mean(ratios)
        suggest = cap(lv) * 0.5 / avg if avg > 0 else None
        ok = lo <= avg <= hi
        want.setdefault(lv, []).append((region, suggest if not ok else cap(lv)))
        rows.append((region, lv, cap(lv), total, len(runs), f'{avg:.0%}',
                     '-' if ok or suggest is None else f'{suggest:.0f}', '통과' if ok else '벗어남'))
    table(('구역', '기준Lv', '지금 용량', '대상 화면', '측정', '평균 비율', '제안 용량', '판정'), rows)
    if skipped:
        print(f'(기준 레벨이 아닌 explore 기록 {skipped}개는 뺐다)')
    # 레벨이 오를수록 용량은 앞 레벨 × BREATH_LEVEL_MIN_STEP 이상 (3.3). 한 레벨에 구역이 둘이면(Lv5 = R5·R6) 큰 값
    print('\n레벨별 제안 (앞 레벨 × {:.2f} 하한 적용):'.format(config.BREATH_LEVEL_MIN_STEP))
    prev = None
    rows = []
    for lv in range(1, len(config.BREATH_CAPACITY)):
        cands = want.get(lv)
        value = max(v for _, v in cands) if cands else cap(lv)
        note = '' if cands else '측정 없음 (지금 값)'
        if prev is not None and value < prev * config.BREATH_LEVEL_MIN_STEP:
            value = prev * config.BREATH_LEVEL_MIN_STEP
            note = (note + ' ' if note else '') + '하한 적용'
        rows.append((f'Lv{lv}', cap(lv), round(value), ', '.join(r for r, _ in cands) if cands else '-', note))
        prev = value
    table(('레벨', '지금', '제안', '근거 구역', '비고'), rows)


# ---------- 2. 구간 (7.6 목표 1·2, 숨예산 3.4) ----------

def segment_table(records, rooms):
    gate_lo, gate_hi = config.BREATH_USE_TARGET['gate']
    seg_max = config.BREATH_USE_TARGET['segment']
    print(f'\n=== 2. 구간표 (게이트 {gate_lo:.0%}~{gate_hi:.0%}, 일반 구간 ≤ {seg_max:.0%}) ===')
    groups = defaultdict(list)
    for r in records:
        if r['type'] != 'segment' or r.get('time', 0) <= 0:
            continue
        if room_of(r['from']) == room_of(r['to']) and r.get('used', 0) <= 0:
            continue   # 같은 방 안에서 숨을 쓰지 않은 기록 (잘못 누른 F6)
        groups[(r['from'], r['to'], r.get('gate'), r['breath_lv'])].append(r)
    rows = []
    for (start, end, gate, lv), runs in sorted(groups.items(), key=lambda kv: (str(kv[0][2]), kv[0][0], kv[0][3])):
        avg = mean([r['used'] for r in runs]) / cap(lv)
        region = rooms.get(room_of(start), (None,))[0]
        ref = config.BREATH_REF_LEVEL.get(region)
        tag = '기준-1' if ref is not None and lv == ref - 1 else ''
        if gate:
            ok = gate_lo <= avg <= gate_hi
            verdict = '통과' if ok else ('통로 줄이기' if avg > gate_hi else '통로 늘리기')
        else:
            ok = avg <= seg_max
            verdict = '통과' if ok else '숨구멍 추가'
        rows.append((gate or '-', start, end, f'Lv{lv}', tag, len(runs), f"{mean([r['time'] for r in runs]):.1f}s",
                     f'{avg:.0%}', verdict))
    if rows:
        table(('게이트', '출발', '도착', '숨Lv', '큰길검사', '측정', '평균 시간', '평균 비율', '판정'), rows)
    else:
        print('측정 없음')
    print('(큰길 검사 = 그 구역 기준 레벨 − 1로 잰 기록. 큰길·곁길 구분은 사람이 본다, 숨예산 3.4)')


# ---------- 3. 보스 (숨예산 5.4, 5.5) ----------

def boss_table(records):
    print('\n=== 3. 보스표 (공격의 n/8을 패링하면 숨 유지: BOSS_PARRY_BREATH = 8 × d ÷ (n × a)) ===')
    groups = defaultdict(list)
    for r in records:
        if r['type'] == 'boss':
            groups[(r['boss'], r['phase'])].append(r)
    scope = SCOPE_BOSSES.get(config.SCOPE)
    rows = []
    best = {}   # 보스 → (값, 페이즈)
    for (boss, phase), runs in sorted(groups.items()):
        if scope and boss not in scope:
            continue
        time = sum(r['time'] for r in runs)
        attacks = sum(r['attacks'] for r in runs)
        if time <= 0 or attacks <= 0:
            continue
        a = attacks / time
        d = sum(r['drain'] for r in runs) / time
        w = sum(r['white'] for r in runs) / attacks
        parry = sum(r['parries'] for r in runs) / attacks
        n = config.BOSS_REGION_N[boss]
        f = n / config.BOSS_PARRY_SHARE_DIV
        note = ''
        if w < f + config.BOSS_PARRY_MARGIN:
            f = w - config.BOSS_PARRY_MARGIN   # 흰 공격이 모자람 → 필요한 패링 비율을 낮춰 숨을 키운다 (5.5)
            note = f'흰 공격 부족 → f={f:.2f}'
        value = d / (f * a) if f > 0 else None
        if value is None:
            note = '흰 공격이 너무 적어 계산 불가'
        elif value > best.get(boss, (0, 0))[0]:
            best[boss] = (value, phase)
        wins = sum(1 for r in runs if r.get('won'))
        rows.append((boss, f'P{phase}', len(runs), wins, f'{time:.0f}s', f'{a:.2f}', f'{d:.2f}', f'{w:.0%}',
                     f'{n}/8', f'{parry:.0%}', '-' if value is None else f'{value:.1f}', note))
    if not rows:
        print('측정 없음')
        return
    table(('보스', '페이즈', '판', '승', '전투 시간', 'a(공격/s)', 'd(숨/s)', '흰 비율', '유지 비율',
           '실제 패링', '계산값', '비고'), rows)
    print('\n보스별 제안 (페이즈 중 가장 큰 값, 숨예산 5.4):')
    rows = []
    for boss, (value, phase) in sorted(best.items()):
        now = config.BOSS_PARRY_BREATH.get(boss)
        rows.append((boss, now, f'{value:.1f}', f'P{phase}', f'{value - now:+.1f}' if now is not None else '-'))
    table(('보스', '지금', '제안', '정한 페이즈', '차이'), rows)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, config.BREATH_BUDGET_PATH)
    if not os.path.exists(path):
        print(f'기록 파일이 없다: {path}')
        return
    records = load_records(path)
    rooms = load_rooms()
    print(f'기록 {len(records)}줄 ({path}), SCOPE {config.SCOPE}')
    explore_table(records, rooms)
    segment_table(records, rooms)
    boss_table(records)


if __name__ == '__main__':
    main()

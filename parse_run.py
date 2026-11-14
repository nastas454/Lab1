#!/usr/bin/env python3

import re, sys, statistics as st

def parse(path):
    stages, cur = [], None
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = re.search(r"Етап: (.+?) \| Задана інтенсивність: (\d+) RPS", line)
        if m:
            cur = {"name": m.group(1), "rate": int(m.group(2)), "rows": []}
            stages.append(cur); continue
        m = re.match(r"\s*(\d+) \|\s*(\d+) \|\s*(\d+) \|\s*(\d+) \|\s*(\d+) \|\s*(\d+) \|\s*([\d.]+) \|\s*([\d.]+) \|\s*([\d.]+)", line)
        if m and cur: cur["rows"].append([float(x) for x in m.groups()])
    return [s for s in stages if len(s["rows"]) >= 30]

for path in sys.argv[1:]:
    print(f"\n=== {path}")
    res = []
    for s in parse(path):
        w = s["rows"][10:]
        ach = [r[3] for r in w]; mean = st.mean(ach)
        ok = mean >= 0.9 * s["rate"]
        res.append((s, mean, ok))
        print(f"{s['name']:<18} задано {s['rate']:>5}  X={mean:7.2f}  розкид={max(ach)-min(ach):4.0f} "
              f"(min {min(ach):.0f}, max {max(ach):.0f})  p99 мед={st.median(r[8] for r in w):7.1f} "
              f"макс={max(r[8] for r in w):7.1f} мс  не-2xx={sum(r[4] for r in w):5.0f}  "
              f"пом.з'єдн={sum(r[5] for r in w):4.0f}  {'OK' if ok else 'НЕВДАЛО'}")
    good = [i for i, (_, _, ok) in enumerate(res) if ok]
    if not good: print("X(N): жодна сходинка не пройшла"); continue
    i = good[-1]
    reached = any(not ok for _, _, ok in res[i + 1:])
    print(f"=> X(N) = {res[i][1]:.2f} RPS на сходинці {res[i][0]['rate']}; "
          f"{'ДОСЯГНУТА (далі була невдала сходинка)' if reached else 'НЕДОСЯГНУТА: додайте вищі сходинки'}")

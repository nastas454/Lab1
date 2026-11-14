#!/usr/bin/env python3

import argparse, json, statistics as st, urllib.parse, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--start", type=float, required=True)
ap.add_argument("--prom", default="http://localhost:9090")
ap.add_argument("--duration", type=int, default=30)
a = ap.parse_args()
t = a.start + a.duration


def q(expr):
    url = f"{a.prom}/api/v1/query?" + urllib.parse.urlencode({"query": expr, "time": t})
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)["data"]["result"]


def by_pod(expr):
    return {x["metric"].get("pod", "?"): float(x["value"][1]) for x in q(expr)}


job = '{job=~".*web.*"}'
rps = by_pod(f'sum by (pod)(rate(http_request_duration_seconds_count{job}[20s]))')
thr = by_pod('sum by (pod)(rate(container_cpu_cfs_throttled_periods_total{container="web"}[20s]))'
             ' / sum by (pod)(rate(container_cpu_cfs_periods_total{container="web"}[20s])) * 100')
p99p = by_pod(f'histogram_quantile(0.99, sum by (le, pod)(rate(http_request_duration_seconds_bucket{job}[20s]))) * 1000')
p99all = q(f'histogram_quantile(0.99, sum by (le)(rate(http_request_duration_seconds_bucket{job}[20s]))) * 1000')
p99all = float(p99all[0]["value"][1]) if p99all else float("nan")

pods = sorted(set(rps) | set(thr) | set(p99p))
print(f"Вікно: [{a.start + 10:.0f}, {t:.0f}] (unix)")
print(f"{'под':<34}{'RPS':>8}{'p99 серв., мс':>16}{'дросель., %':>13}")
for p in pods:
    print(f"{p:<34}{rps.get(p, float('nan')):8.1f}{p99p.get(p, float('nan')):16.2f}{thr.get(p, float('nan')):13.2f}")
r = [rps[p] for p in pods if p in rps]
if r:
    print(f"\nСума RPS = {sum(r):.1f} (має збігатися з X(N) ±1-2); середнє = {st.mean(r):.1f}; "
          f"I = max/середнє = {max(r) / st.mean(r):.3f}")
tv = [thr[p] for p in pods if p in thr]
if tv:
    print(f"Дроселювання CPU: середнє за подами = {st.mean(tv):.2f} %, максимум = {max(tv):.2f} %")
print(f"p99 сервера (усі поди разом) = {p99all:.2f} мс")
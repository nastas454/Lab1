import os
import json
import urllib.request
import urllib.parse

PROM_URL = "http://localhost:9090"

def query_prom(expr, ts):
    params = urllib.parse.urlencode({"query": expr, "time": f"{ts:.1f}"})
    url = f"{PROM_URL}/api/v1/query?{params}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("data", {}).get("result", [])
    except Exception:
        return []

all_runs = [
    (1, 200, "run_N1.txt", 2, ("web-6989949b6c-bxgmx", 199.9), ("web-6989949b6c-bxgmx", 199.9), 1.000),
    (2, 200, "run_N2.txt", 2, ("web-6989949b6c-wflzn", 108.7), ("web-6989949b6c-bxgmx", 91.3), 1.087),
    (3, 600, "run_N3.txt", 2, ("web-6989949b6c-bxgmx", 191.9), ("web-6989949b6c-wflzn", 186.8), 1.014),
    (5, 800, "run_N5.txt", 2, ("web-6989949b6c-j9b7k", 168.9), ("web-6989949b6c-wflzn", 133.0), 1.132),
]

q_p99_all = 'histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{job=~".*web.*"}[30s]))) * 1000'
q_p99_pod = 'histogram_quantile(0.99, sum by (pod, le) (rate(http_request_duration_seconds_bucket{job=~".*web.*"}[30s]))) * 1000'
q_thr_pod = '(sum by (pod) (rate(container_cpu_cfs_throttled_periods_total{container="web"}[30s])) / sum by (pod) (rate(container_cpu_cfs_periods_total{container="web"}[30s]))) * 100'

print("=" * 85)
print("ПОВНІ МЕТРИКИ PROMETHEUS ДЛЯ КРОКУ 7 (на сходинці X(N))")
print("=" * 85)
print(f"{'N':<4} | {'Сходинка':<10} | {'p99 сервера (мс)':<18} | {'Сер. дросель (%)':<18} | {'Макс. дросель (%)':<18}")
print("-" * 85)

step8_data = []

for n, step_rps, fname, failed_steps, max_p, min_p, imb_i in all_runs:
    ts = os.path.getmtime(fname) - (failed_steps * 30.0) - 1.0
    res_p99_all = query_prom(q_p99_all, ts)
    val_p99_all = float(res_p99_all[0]["value"][1]) if res_p99_all and res_p99_all[0]["value"][1] != "NaN" else 0.0

    p99_by_pod = {}
    for r in query_prom(q_p99_pod, ts):
        pod_name = r["metric"].get("pod") or r["metric"].get("pod_name") or ""
        if r["value"][1] != "NaN":
            p99_by_pod[pod_name] = float(r["value"][1])

    thr_by_pod = {}
    for r in query_prom(q_thr_pod, ts):
        pod_name = r["metric"].get("pod") or r["metric"].get("pod_name") or ""
        if r["value"][1] != "NaN":
            thr_by_pod[pod_name] = float(r["value"][1])

    if not thr_by_pod:
        q_thr_45 = q_thr_pod.replace("[30s]", "[45s]")
        for r in query_prom(q_thr_45, ts):
            pod_name = r["metric"].get("pod") or r["metric"].get("pod_name") or ""
            if r["value"][1] != "NaN":
                thr_by_pod[pod_name] = float(r["value"][1])

    thr_vals = list(thr_by_pod.values())
    avg_thr = sum(thr_vals) / len(thr_vals) if thr_vals else 0.0
    max_thr = max(thr_vals) if thr_vals else 0.0

    print(f"{n:<4} | {f'{step_rps} RPS':<10} | {val_p99_all:<18.2f} | {avg_thr:<18.2f} | {max_thr:<18.2f}")

    if n > 1:
        step8_data.append((n, step_rps, imb_i, max_p, min_p, p99_by_pod, thr_by_pod))

print("\n" + "=" * 95)
print("ТАБЛИЦЯ ДЛЯ КРОКУ 8 (Метрики для найзавантаженішого і найменш завантаженого подів)")
print("=" * 95)

for n, step_rps, imb_i, (max_pod, max_rps), (min_pod, min_rps), p99_by_pod, thr_by_pod in step8_data:
    print(f"\nN = {n} (Сходинка {step_rps} RPS) | Коефіцієнт дисбалансу I = {imb_i:.3f}")
    print(f"  [Найзавантаженіший]    {max_pod} ({max_rps:5.1f} RPS) -> "
          f"p99 сервера: {p99_by_pod.get(max_pod, 0.0):6.2f} мс | Дроселювання CPU: {thr_by_pod.get(max_pod, 0.0):6.2f} %")
    print(f"  [Найменш завантажений] {min_pod} ({min_rps:5.1f} RPS) -> "
          f"p99 сервера: {p99_by_pod.get(min_pod, 0.0):6.2f} мс | Дроселювання CPU: {thr_by_pod.get(min_pod, 0.0):6.2f} %")
#!/usr/bin/env python3
import argparse, csv, json, statistics as st, subprocess, sys, time
import urllib.parse, urllib.request

NA = "не досягнуто"


def kubectl(*a):
    return subprocess.run(["kubectl", *a], capture_output=True, text=True).stdout.strip()


def cmd_wait(args):
    """Чекає, поки HPA показує 1 репліку (бажану і поточну) 60 с безперервно."""
    streak_start = None
    while True:
        cur = kubectl("get", "hpa", args.hpa, "-o", "jsonpath={.status.currentReplicas}")
        des = kubectl("get", "hpa", args.hpa, "-o", "jsonpath={.status.desiredReplicas}")
        ready = kubectl("get", "deploy", "web", "-o", "jsonpath={.status.readyReplicas}")
        ok = cur == "1" and des == "1" and ready == "1"
        now = time.time()
        if ok:
            streak_start = streak_start or now
        else:
            streak_start = None
        held = 0 if streak_start is None else now - streak_start
        print(f"current={cur or '-'} desired={des or '-'} ready={ready or '-'}  1 репліка вже {held:4.0f} с")
        if held >= args.hold:
            print("Готово: можна запускати прогін.")
            return
        time.sleep(2)


def prom_series(url, query, t0, n):
    """Ряд на сітці t0, t0+1, ..., t0+n-1; прогалини заповнюються попереднім значенням."""
    q = urllib.parse.urlencode({"query": query, "start": t0, "end": t0 + n - 1, "step": 1})
    with urllib.request.urlopen(f"{url}/api/v1/query_range?{q}", timeout=30) as r:
        data = json.load(r)
    res = data["data"]["result"]
    vals = {}
    if res:
        for ts, v in res[0]["values"]:
            vals[int(round(float(ts) - t0))] = float(v)
    out, last = [], None
    for i in range(n):
        last = vals.get(i, last)
        out.append(last)
    return out


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def events(p99, seg, desired, ready, ref_p99_spike, hold=10, factor=1.2):
    n = len(p99)
    s0 = seg.index(2)
    s1 = n - seg[::-1].index(2)
    base = desired[s0]
    t1 = next((t - s0 for t in range(s0 + 1, s1) if desired[t] is not None and desired[t] != base), None)
    mx = max(v for v in ready if v is not None)
    t2 = None
    if mx > ready[s0]:
        t = next(t for t in range(n) if ready[t] == mx)
        if s0 < t < s1:
            t2 = t - s0
    thr = factor * ref_p99_spike
    t3 = None
    for i in range(s0, s1 - hold + 1):
        w = p99[i:i + hold]
        if all(0 < x < thr for x in w):
            t3 = i - s0
            break
    t4 = next((t - s1 for t in range(s1 + 1, n)
               if ready[t] is not None and ready[t - 1] is not None and ready[t] < ready[t - 1]), None)
    return (t1, t2, t3, t4), dict(s0=s0, s1=s1, max_ready=mx, thr=thr, base_desired=base)

def fmt(t):
    return NA if t is None else f"{t} с"

def cmd_analyze(args):
    run = read_csv(args.csv)
    ref = read_csv(args.ref_csv)
    n = len(run)
    t0 = float(run[0]["unix_start"])
    seg = [int(r["segment"]) for r in run]
    p99 = [float(r["p99_ms"]) for r in run]
    sp = [float(r["p99_ms"]) for r in ref if int(r["segment"]) == 2]
    ref_p99 = {"median": st.median, "mean": st.mean, "max": max}[args.ref_stat](sp)
    if args.offset is None:
        before = time.time()
        with urllib.request.urlopen(f"{args.prom}/api/v1/query?query=time()", timeout=30) as r:
            prom_now = float(json.load(r)["data"]["result"][1])  # скаляр: [мітка, "значення"]
        offset = round(prom_now - (before + time.time()) / 2)
    else:
        offset = args.offset
    print(f"Зсув годинника Prometheus відносно генератора: {offset:+d} с (застосовано)")
    t0_local, t0 = t0, t0 + offset

    desired = prom_series(args.prom, f'max(kube_horizontalpodautoscaler_status_desired_replicas{{horizontalpodautoscaler="{args.hpa}"}})', t0, n)
    ready = prom_series(args.prom, 'sum(kube_deployment_status_replicas_ready{deployment="web"})', t0, n)
    cpu = prom_series(args.prom, f'avg(rate(container_cpu_usage_seconds_total{{container="web",pod=~"web-.*"}}[15s])) / {args.req_cpu}', t0, n)
    if None in (desired[0], ready[0]):
        sys.exit("Prometheus не повернув ряди за інтервал прогону (перевірте --prom і назви метрик).")

    (t1, t2, t3, t4), info = events(p99, seg, desired, ready, ref_p99)
    print(f"Початок профілю: unix {t0_local:.3f}; стрибок {info['s0']}–{info['s1']} с профілю")
    print(f"Еталон p99 стрибка (крок 10, {args.ref_stat}): {ref_p99:.1f} мс -> поріг 1,2·p99 = {info['thr']:.1f} мс")
    print(f"Бажана кількість реплік до стрибка: {info['base_desired']:.0f}; найбільша кількість готових: {info['max_ready']:.0f}\n")
    print(f"1. стрибок -> перша зміна бажаної кількості реплік:        {fmt(t1)}")
    print(f"2. стрибок -> готовність найбільшої кількості реплік:      {fmt(t2)}")
    print(f"3. стрибок -> p99 10 с поспіль < 1,2·p99 кроку 10:         {fmt(t3)}")
    print(f"4. кінець стрибка -> перше зменшення готових реплік:       {fmt(t4)}")

    out = "step11_series.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sec", "segment", "expected", "ok_2xx", "p99_ms", "desired", "ready", "cpu_util_vs_requests"])
        for i, r in enumerate(run):
            w.writerow([r["sec"], r["segment"], r["expected"], r["ok_2xx"], r["p99_ms"], desired[i], ready[i],
                        "" if cpu[i] is None else f"{cpu[i]:.3f}"])
    print(f"\nПосекундні ряди для кроку 12 збережено: {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wait"); w.add_argument("--hpa", default="web"); w.add_argument("--hold", type=int, default=60)
    a = sub.add_parser("analyze")
    a.add_argument("--csv", required=True); a.add_argument("--ref-csv", required=True)
    a.add_argument("--prom", default="http://localhost:9090"); a.add_argument("--hpa", default="web")
    a.add_argument("--ref-stat", default="median", choices=["median", "mean", "max"])
    a.add_argument("--req-cpu", type=float, default=0.25)
    a.add_argument("--offset", type=int, default=None, help="зсув годинника Prometheus, с (за замовчуванням вимірюється)")
    args = ap.parse_args()
    {"wait": cmd_wait, "analyze": cmd_analyze}[args.cmd](args)
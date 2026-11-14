import argparse, json, sys, urllib.parse, urllib.request
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROM = "http://localhost:9090"
T = 180
X1, X2, X3, X5 = 199.90, 406.55, 567.65, 746.05
KAPPA = 0.01613638547841258
R = 5
XN = {1: X1, 2: X2, 3: X3, 4: X1 * 4 / (1 + KAPPA * 4 * 3), 5: X5}

def d_of(z):
    for n in range(1, R + 1):
        if XN[n] >= z:
            return n
    return R

def qrange(q, start):
    url = PROM + "/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": q, "start": start, "end": start + T, "step": 1})
    with urllib.request.urlopen(url, timeout=30) as r:
        res = json.load(r)["data"]["result"]
    if not res:
        sys.exit("Prometheus повернув порожній результат для: " + q)
    out = {int(round(float(t) - start)): float(v) for t, v in res[0]["values"]}
    arr, last = [], np.nan
    for i in range(T):
        last = out.get(i, last)
        arr.append(last)
    return np.array(arr)

def load(path):
    df = pd.read_csv(path).iloc[-T:].reset_index(drop=True)
    if len(df) != T:
        sys.exit(f"{path}: очікував {T} рядків, є {len(df)}")
    c = df.shape[1]
    g = lambda k: pd.to_numeric(df.iloc[:, c + k], errors="coerce").fillna(0).to_numpy()
    d = dict(target=g(-8), sent=g(-7), ok=g(-6), non2xx=g(-5), conn=g(-4), p99=g(-1))
    if not set(np.unique(d["target"])) <= {60.0, 400.0}:
        sys.exit(f"{path}: стовпець 'задано' містить {np.unique(d['target'])}; покажіть мені заголовок CSV")
    return d

def metrics(d, s, thr):
    dd = np.array([d_of(z) for z in d["target"]])
    return dd, {
        "theta_U": np.mean(s < dd), "theta_O": np.mean(s > dd),
        "a_U": np.mean(np.maximum(dd - s, 0)), "a_O": np.mean(np.maximum(s - dd, 0)),
        "W (репліко-с)": s.sum(),
        "с порушення порогу": int((d["p99"] > thr).sum()),
        "не-2xx": int(d["non2xx"].sum()), "помилки з'єдн.": int(d["conn"].sum()),
    }

ap = argparse.ArgumentParser()
ap.add_argument("--run10", default="profile_run.csv")
ap.add_argument("--start10", type=float, default=1794444822.295)
ap.add_argument("--run11", default="step11_hpa_run2.csv")
ap.add_argument("--start11", type=float, default=1794448063.790)
a = ap.parse_args()

r10, r11 = load(a.run10), load(a.run11)
p99_0 = float(np.median(r10["p99"][:30]))
thr = 2 * p99_0
print(f"p99_0 = {p99_0:.1f} мс -> поріг 2·p99_0 = {thr:.1f} мс")
print("d(t): z=60 ->", d_of(60), "; z=400 ->", d_of(400), f"(X(1)={XN[1]}, X(2)={XN[2]})")

Q_S = 'sum(kube_deployment_status_replicas_ready{deployment="web"})'
Q_C = '100*avg(sum by (pod)(rate(container_cpu_usage_seconds_total{container="web",pod=~"web-.*"}[20s])))/0.25'
runs = {}
for name, d, st in (("Крок 10 (фіксовано R=5)", r10, a.start10), ("Крок 11 (HPA)", r11, a.start11)):
    s, cpu = qrange(Q_S, st), qrange(Q_C, st)
    dd, m = metrics(d, s, thr)
    runs[name] = (d, s, dd, cpu)
    print("\n" + name)
    for k, v in m.items():
        print(f"  {k:22s} {v:.4f}" if isinstance(v, float) else f"  {k:22s} {v}")
    pd.DataFrame({"t": range(T), "z": d["target"], "ok": d["ok"], "p99": d["p99"],
                  "d": dd, "s": s, "cpu_pct": cpu}).to_csv(
        "step12_" + ("step10" if "10" in name else "step11") + ".csv", index=False)

fig, ax = plt.subplots(4, 2, sharex=True, sharey="row", figsize=(14, 13))
t = np.arange(T)
for j, (name, (d, s, dd, cpu)) in enumerate(runs.items()):
    ax[0, j].set_title(name)
    ax[0, j].plot(t, d["target"], label="задана"); ax[0, j].plot(t, d["ok"], label="досягнута (2xx)", alpha=.8)
    ax[0, j].set_ylabel("RPS"); ax[0, j].legend()
    ax[1, j].plot(t, np.maximum(d["p99"], 0.1)); ax[1, j].axhline(thr, ls="--", c="r", label=f"поріг {thr:.0f} мс")
    ax[1, j].set_yscale("log"); ax[1, j].set_ylabel("p99 клієнта, мс"); ax[1, j].legend()
    ax[2, j].step(t, dd, where="post", label="d(t)"); ax[2, j].step(t, s, where="post", label="s(t)")
    ax[2, j].set_ylabel("репліки"); ax[2, j].set_ylim(0, 5.5); ax[2, j].legend()
    ax[3, j].plot(t, cpu); ax[3, j].axhline(70, ls="--", c="gray", label="ціль 70 %")
    ax[3, j].set_ylabel("CPU / requests, %"); ax[3, j].set_xlabel("секунда прогону"); ax[3, j].legend()
for r_ in ax:
    for x_ in r_: x_.grid(alpha=.3)
plt.tight_layout(); plt.savefig("step12_charts.png", dpi=130)
print("\nДіаграми: step12_charts.png; ряди: step12_step10.csv, step12_step11.csv")
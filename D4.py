import argparse, json, sys, urllib.parse, urllib.request
import numpy as np, pandas as pd

PROM = "http://localhost:9090"
ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
ap.add_argument("--start", type=float, required=True)
ap.add_argument("--t0", type=float, required=True)
ap.add_argument("--t1", type=float, required=True)
ap.add_argument("--tail", type=float, default=30, help="скільки секунд після кінця drain ще дивитись")
a = ap.parse_args()

df = pd.read_csv(a.csv).iloc[-180:].reset_index(drop=True)
c = df.shape[1]
g = lambda k: pd.to_numeric(df.iloc[:, c + k], errors="coerce").fillna(0).to_numpy()
non2, conn, p99 = g(-5), g(-4), g(-1)
i0, i1 = max(int(a.t0 - a.start), 0), min(int(a.t1 + a.tail - a.start) + 1, 180)
print(f"drain тривав {a.t1 - a.t0:.0f} с; вікно аналізу: секунди {i0}..{i1} прогону")
print(f"у вікні: не-2xx = {int(non2[i0:i1].sum())}, помилки з'єдн. = {int(conn[i0:i1].sum())}, "
      f"p99 мед = {np.median(p99[i0:i1]):.1f} макс = {p99[i0:i1].max():.1f} мс")
print(f"за весь прогін: не-2xx = {int(non2.sum())}, помилки з'єдн. = {int(conn.sum())}")

def q(query):
    url = PROM + "/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": query, "start": a.t0 - 5, "end": a.t1 + a.tail, "step": 1})
    with urllib.request.urlopen(url, timeout=30) as r:
        res = json.load(r)["data"]["result"]
    return [float(v) for _, v in res[0]["values"]] if res else []

for name, m in (("готові (ready)", "kube_deployment_status_replicas_ready"),
                ("доступні (available)", "kube_deployment_status_replicas_available")):
    v = q(f'sum({m}{{deployment="web"}})')
    print(f"поди {name}: мін = {min(v):.0f}, макс = {max(v):.0f}" if v else f"поди {name}: немає даних")
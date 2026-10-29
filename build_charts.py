import datetime
import requests
import matplotlib.pyplot as plt

LOG_FILE = "web-4.txt"
START_TIME_STR = "2026-10-29 20:52:35"
PROM_URL = "http://localhost:9090"

client_t, target_rps, achieved_rps, client_p99 = [], [], [], []
current_t = 0

with open(LOG_FILE, 'r', encoding='utf-8') as f:
    for line in f:
        parts = [p.strip() for p in line.split('|')]
        if len(parts) == 9 and parts[0].isdigit():
            current_t += 1
            client_t.append(current_t)
            target_rps.append(int(parts[1]))
            achieved_rps.append(int(parts[3]))
            client_p99.append(float(parts[8]))

dt_start = datetime.datetime.strptime(START_TIME_STR, "%Y-%m-%d %H:%M:%S")
ts_start = dt_start.timestamp()
ts_end = ts_start + current_t

def query_prom(query, step="1s"):
    res = requests.get(f"{PROM_URL}/api/v1/query_range", params={
        "query": query, "start": ts_start, "end": ts_end, "step": step
    })
    return res.json()['data']['result']

q_p99_20s = "histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[20s]))) * 1000"
q_p99_15s = "histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[15s]))) * 1000"
q_rps = "sum by (instance) (rate(http_request_duration_seconds_count[20s]))"
q_cpu = "rate(process_cpu_seconds_total[20s])"
q_inprog = "http_requests_in_progress"

print("Завантаження даних з Prometheus...")
data_p99_20s = query_prom(q_p99_20s)
data_p99_15s = query_prom(q_p99_15s, step="5s")
data_rps = query_prom(q_rps)
data_cpu = query_prom(q_cpu)
data_inprog = query_prom(q_inprog)

def extract_xy(prom_result):
    if not prom_result: return [], []
    vals = prom_result[0]['values']
    x = [float(v[0]) - ts_start for v in vals]
    y = [float(v[1]) if v[1] != 'NaN' else 0 for v in vals]
    return x, y

def extract_multi_xy(prom_result):
    lines = []
    for res in prom_result:
        inst = res['metric'].get('instance', 'unknown')
        if 'postgres' in inst: continue
        vals = res['values']
        x = [float(v[0]) - ts_start for v in vals]
        y = [float(v[1]) if v[1] != 'NaN' else 0 for v in vals]
        lines.append((inst, x, y))
    return lines

fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

ax1.plot(client_t, target_rps, label="Задана інтенсивність (Client)", color='blue', linestyle='--')
ax1.plot(client_t, achieved_rps, label="Досягнута інтенсивність 2xx (Client)", color='green')
ax1.set_ylabel("RPS")
ax1.set_title("Інтенсивність навантаження")
ax1.legend()
ax1.grid(True, alpha=0.5)

ax2.plot(client_t, client_p99, label="p99 клієнта", color='red')
x, y = extract_xy(data_p99_20s)
if x: ax2.plot(x, y, label="p99 сервера (вікно 20s)", color='purple', alpha=0.7)
x, y = extract_xy(data_p99_15s)
if x: ax2.plot(x, y, label="p99 сервера (вікно 15s, крок 5s)", color='orange', drawstyle='steps-post')
ax2.set_ylabel("Затримка (мс)")
ax2.set_title("Затримки (p99)")
ax2.legend()
ax2.grid(True, alpha=0.5)

ax3_cpu = ax3.twinx()
colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red']

for i, (inst, x, y) in enumerate(extract_multi_xy(data_rps)):
    ax3.plot(x, y, label=f"RPS [{inst}]", linestyle='-', color=colors[i%len(colors)])
for i, (inst, x, y) in enumerate(extract_multi_xy(data_inprog)):
    ax3.plot(x, y, label=f"В обробці [{inst}]", linestyle=':', linewidth=2, color=colors[i%len(colors)])
for i, (inst, x, y) in enumerate(extract_multi_xy(data_cpu)):
    ax3_cpu.plot(x, y, label=f"CPU [{inst}]", linestyle='--', alpha=0.6, color=colors[i%len(colors)])

ax3.set_ylabel("RPS / К-сть в обробці")
ax3_cpu.set_ylabel("Використання CPU")
ax3.set_xlabel("Час (секунди від початку тесту)")
ax3.set_title("Метрики екземплярів")

lines_1, labels_1 = ax3.get_legend_handles_labels()
lines_2, labels_2 = ax3_cpu.get_legend_handles_labels()
ax3.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left', bbox_to_anchor=(1.05, 1))

plt.tight_layout()
plt.savefig(f"chart_{LOG_FILE.replace('.txt', '')}.png", dpi=150)
print(f"Графік успішно збережено як chart_{LOG_FILE.replace('.txt', '')}.png")
plt.show()
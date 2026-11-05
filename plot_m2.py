import requests
import datetime
import matplotlib.pyplot as plt

PROM_URL = "http://localhost:9090"

START_TIME_N1 = "2026-10-29 20:43:29"
START_TIME_N4 = "2026-10-29 20:52:35"

stages_n1 = [
    {"rps": 200, "start_sec": 10, "end_sec": 30},
    {"rps": 400, "start_sec": 30, "end_sec": 50},
    {"rps": 600, "start_sec": 50, "end_sec": 70},
]

stages_n4 = [
    {"rps": 200, "start_sec": 10, "end_sec": 30},
    {"rps": 400, "start_sec": 30, "end_sec": 50},
    {"rps": 600, "start_sec": 50, "end_sec": 70},
    {"rps": 800, "start_sec": 70, "end_sec": 90},
    {"rps": 1000, "start_sec": 90, "end_sec": 110},
]

def get_prom_data(start_str, stages):
    dt_start = datetime.datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    ts_start = dt_start.timestamp()
    rps_list = []
    conn_list = []
    for stage in stages:
        q_start = ts_start + stage["start_sec"]
        q_end = ts_start + stage["end_sec"]
        query = 'sum(pg_stat_activity_count{state="active"})'
        try:
            res = requests.get(f"{PROM_URL}/api/v1/query_range", params={
                "query": query, "start": q_start, "end": q_end, "step": "1s"
            }).json()
            max_val = 0
            if res.get('data') and res.get('data').get('result'):
                vals = [float(v[1]) for v in res['data']['result'][0]['values']]
                max_val = max(vals) if vals else 0
            rps_list.append(stage["rps"])
            conn_list.append(max_val)
        except Exception as e:
            print(f"Помилка Prometheus: {e}")
            rps_list.append(stage["rps"])
            conn_list.append(0)
    return rps_list, conn_list

print("Отримання даних з Prometheus...")
rps_n1, conn_n1 = get_prom_data(START_TIME_N1, stages_n1)
rps_n4, conn_n4 = get_prom_data(START_TIME_N4, stages_n4)

plt.figure(figsize=(10, 6))
plt.plot(rps_n1, conn_n1, marker='o', linestyle='-', color='blue', label='N = 1', markersize=8)
plt.plot(rps_n4, conn_n4, marker='s', linestyle='-', color='green', label='N = 4', markersize=8)
plt.title('Залежність кількості активних з\'єднань БД від заданої інтенсивності')
plt.xlabel('Задана інтенсивність (RPS)')
plt.ylabel('Активні з\'єднання (pg_stat_activity_count)')
plt.xticks([200, 400, 600, 800, 1000])
plt.legend()
plt.grid(True, linestyle='--', alpha=0.7)

plt.axhline(y=10, color='blue', linestyle=':', alpha=0.5)
plt.axhline(y=40, color='green', linestyle=':', alpha=0.5)
plt.text(200, 11, 'Ліміт пулу (N=1)', color='blue', fontsize=9)
plt.text(200, 41, 'Ліміт пулу (N=4)', color='green', fontsize=9)

plt.tight_layout()
plt.savefig('m2_metric_chart.png', dpi=150)
print("Діаграму успішно збережено як m2_metric_chart.png")
plt.show()
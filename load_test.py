import time
import random
import requests
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
import argparse

WARMUP_SEC = 10
RUN_SEC = 30
TOTAL_SEC = WARMUP_SEC + RUN_SEC
URL_TEMPLATE = "http://localhost/dispensary/{}"

def fetch(expected_start, valid_ids):
    record_id = random.choice(valid_ids)
    actual_start = time.time()
    try:
        r = requests.get(URL_TEMPLATE.format(record_id), timeout=5.0)
        status = r.status_code
    except Exception:
        status = 0
    actual_end = time.time()
    return (expected_start, actual_start, actual_end, status)

def worker(args):
    target_rps_per_worker, valid_ids = args
    total_requests = target_rps_per_worker * TOTAL_SEC
    interval = 1.0 / target_rps_per_worker
    results = []
    with ThreadPoolExecutor(max_workers=target_rps_per_worker * 2) as executor:
        futures = []
        base_time = time.time()
        for i in range(total_requests):
            expected_start = base_time + i * interval
            now = time.time()
            if expected_start > now:
                time.sleep(expected_start - now)
            futures.append(executor.submit(fetch, expected_start, valid_ids))
        for f in futures:
            results.append(f.result())
    return results

def main(total_rps):
    try:
        with open("ids.txt", "r") as f:
            valid_ids = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Файл ids.txt не знайдено. Спочатку запустіть populate.py")
        return
    cores = multiprocessing.cpu_count()
    if cores > total_rps:
        cores = total_rps
    rps_per_worker = total_rps // cores
    actual_total_rps = rps_per_worker * cores

    print(f"Запуск: {actual_total_rps} RPS ({rps_per_worker} RPS на кожен з {cores} процесів)")

    with multiprocessing.Pool(cores) as pool:
        results = pool.map(worker, [(rps_per_worker, valid_ids)] * cores)

    flat_results = [item for sublist in results for item in sublist]
    min_expected = min(r[0] for r in flat_results)
    valid_results = [r for r in flat_results if r[0] >= min_expected + WARMUP_SEC]
    total_valid = len(valid_results)
    if total_valid == 0:
        print("Немає успішних запитів після прогріву.")
        return

    latencies = []
    errors = 0
    sum_time_in_system = 0.0
    for req in valid_results:
        exp_start, act_start, act_end, status = req
        if 200 <= status < 300:
            latency = act_end - act_start
            latencies.append(latency)
            sum_time_in_system += (act_end - exp_start)
        else:
            errors += 1
    if not latencies:
        print("Жоден запит не був успішним.")
        return

    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)] * 1000
    p95 = latencies[int(len(latencies) * 0.95)] * 1000
    p99 = latencies[int(len(latencies) * 0.99)] * 1000
    achieved_rps = len(latencies) / RUN_SEC
    error_rate = (errors / total_valid) * 100
    avg_l = sum_time_in_system / RUN_SEC
    avg_w = (sum(latencies) / len(latencies))

    print("-" * 30)
    print(f"Задана інтенсивність: {actual_total_rps} RPS")
    print(f"Досягнута інтенсивність: {achieved_rps:.2f} RPS")
    print(f"p50: {p50:.2f} ms")
    print(f"p95: {p95:.2f} ms")
    print(f"p99: {p99:.2f} ms")
    print(f"Помилки (не 2xx): {error_rate:.2f}%")
    print(f"Для Літтла (100 RPS): λ={achieved_rps:.2f}, W={avg_w:.4f}s, Виміряне L={avg_l:.2f}")
    print("-" * 30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rps", type=int, required=True)
    args = parser.parse_args()
    main(args.rps)
import time
import asyncio
import aiohttp
import random
import sys

URL_TEMPLATE = "http://localhost/dispensary/{}"
TIMEOUT = 5.0

async def fetch(session, expected_start, record_id):
    now = time.time()
    if expected_start > now:
        await asyncio.sleep(expected_start - now)
    actual_start = time.time()
    status = 0
    try:
        async with session.get(URL_TEMPLATE.format(record_id), timeout=TIMEOUT) as response:
            status = response.status
    except asyncio.TimeoutError:
        status = 408
    except Exception:
        status = 0
    actual_end = time.time()
    return expected_start, actual_start, actual_end, status

async def run_step(session, target_rps, duration, valid_ids, step_name):
    total_requests = target_rps * duration
    interval = 1.0 / target_rps

    print(f"\n{'=' * 80}")
    print(f"Етап: {step_name} | Задана інтенсивність: {target_rps} RPS | Тривалість: {duration} с")
    print(f"{'=' * 80}")
    print("Секунда | Задано | Відправлено | Досягнуто(2xx) | Не 2xx | Помилки з'єдн. | p50 (ms) | p95 (ms) | p99 (ms)")

    tasks = []
    base_time = time.time()
    for i in range(total_requests):
        expected_start = base_time + i * interval
        record_id = random.choice(valid_ids)
        tasks.append(asyncio.create_task(fetch(session, expected_start, record_id)))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    per_second_stats = {
        i: {"expected": target_rps, "actual_sent": 0, "2xx": 0, "non_2xx": 0, "conn_err": 0, "latencies": []} for i in
        range(duration)}

    for res in results:
        if isinstance(res, Exception):
            continue
        expected_start, actual_start, actual_end, status = res
        sec_sent = int(actual_start - base_time)
        sec_completed = int(actual_end - base_time)
        if 0 <= sec_sent < duration:
            per_second_stats[sec_sent]["actual_sent"] += 1
        if 0 <= sec_completed < duration:
            if 200 <= status < 300:
                per_second_stats[sec_completed]["2xx"] += 1
                latency_ms = (actual_end - expected_start) * 1000
                per_second_stats[sec_completed]["latencies"].append(latency_ms)
            elif status == 0:
                per_second_stats[sec_completed]["conn_err"] += 1
            else:
                per_second_stats[sec_completed]["non_2xx"] += 1
    step_achieved_rps_list = []

    for sec in range(duration):
        st = per_second_stats[sec]
        lats = sorted(st["latencies"])
        p50 = lats[int(len(lats) * 0.50)] if lats else 0
        p95 = lats[int(len(lats) * 0.95)] if lats else 0
        p99 = lats[int(len(lats) * 0.99)] if lats else 0
        print(
            f"{sec + 1:7d} | {st['expected']:6d} | {st['actual_sent']:11d} | {st['2xx']:14d} | {st['non_2xx']:6d} | {st['conn_err']:14d} | {p50:8.1f} | {p95:8.1f} | {p99:8.1f}")
        if step_name != "Прогрів" and sec >= 5:
            step_achieved_rps_list.append(st['2xx'])

    avg_achieved = sum(step_achieved_rps_list) / len(step_achieved_rps_list) if step_achieved_rps_list else 0
    if step_name != "Прогрів":
        print(
            f"-> Середня досягнута інтенсивність на сходинці: {avg_achieved:.2f} RPS (Поріг 90%: {0.9 * target_rps:.2f} RPS)")
    return avg_achieved

def silence_winerror_10054(loop, context):
    exc = context.get('exception')
    if isinstance(exc, ConnectionResetError) or (isinstance(exc, OSError) and exc.errno == 10054):
        return
    loop.default_exception_handler(context)

async def main():
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(silence_winerror_10054)
    try:
        with open("ids.txt", "r") as f:
            valid_ids = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Файл ids.txt не знайдено. Спочатку запустіть populate.py")
        return

    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(connector=connector) as session:
        await run_step(session, target_rps=200, duration=10, valid_ids=valid_ids, step_name="Прогрів")

        current_rps = 200
        consecutive_fails = 0
        while True:
            avg_achieved = await run_step(session, target_rps=current_rps, duration=20, valid_ids=valid_ids,
                                          step_name=f"Сходинка {current_rps} RPS")

            if avg_achieved < 0.9 * current_rps:
                consecutive_fails += 1
                print(f"[!] УВАГА: Сервер не справляється (Спроба {consecutive_fails}/2).")
            else:
                consecutive_fails = 0

            if consecutive_fails >= 2:
                print(
                    "\n[!] ТЕСТ ЗУПИНЕНО: На двох сходинках поспіль досягнута інтенсивність нижча за 0.9 від заданої.")
                break
            current_rps += 200
    await asyncio.sleep(0.250)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nТест перервано користувачем.")
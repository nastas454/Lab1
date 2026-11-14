import time
import asyncio
import aiohttp
import random
import sys
from collections import Counter

URL_TEMPLATE = "http://127.0.0.1:8080/dispensary/{}"
TIMEOUT = aiohttp.ClientTimeout(total=5.0)
R = 5
NUM_CONNECTIONS = 8 * R
REQUESTS_PER_CONNECTION = 100

async def run_step(target_rps, duration, valid_ids, step_name):
    total_requests = target_rps * duration
    interval = 1.0 / target_rps

    print(f"\n{'=' * 80}")
    print(f"Етап: {step_name} | Задана інтенсивність: {target_rps} RPS | Тривалість: {duration} с")
    print(f"{'=' * 80}")
    print("Секунда | Задано | Відправлено | Досягнуто(2xx) | Не 2xx | Помилки з'єдн. | p50 (ms) | p95 (ms) | p99 (ms)")

    queue = asyncio.Queue()
    stop_event = asyncio.Event()
    results = []

    async def worker():
        while not stop_event.is_set():
            connector = aiohttp.TCPConnector(limit=1)
            async with aiohttp.ClientSession(connector=connector, timeout=TIMEOUT) as session:
                done = 0
                while done < REQUESTS_PER_CONNECTION and not stop_event.is_set():
                    try:
                        expected_start = await asyncio.wait_for(queue.get(), timeout=0.1)
                    except asyncio.TimeoutError:
                        continue

                    record_id = random.choice(valid_ids)
                    actual_start = time.time()
                    status = 0
                    pod = None

                    try:
                        async with session.get(URL_TEMPLATE.format(record_id)) as response:
                            await response.read()
                            status = response.status
                            pod = response.headers.get("X-Pod")
                    except asyncio.TimeoutError:
                        status = 408
                    except Exception:
                        status = 0

                    actual_end = time.time()
                    results.append((expected_start, actual_start, actual_end, status, pod))
                    queue.task_done()
                    done += 1

    workers = [asyncio.create_task(worker()) for _ in range(NUM_CONNECTIONS)]

    base_time = time.time()
    print(f"Початок сходинки (unix, для вікна Prometheus): {base_time:.3f}")

    for i in range(total_requests):
        expected_start = base_time + i * interval
        now = time.time()
        if expected_start > now:
            await asyncio.sleep(expected_start - now)
        queue.put_nowait(expected_start)

    time_to_wait = duration - (time.time() - base_time)
    if time_to_wait > 0:
        await asyncio.sleep(time_to_wait)

    stop_event.set()
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    per_second_stats = {
        i: {"expected": target_rps, "actual_sent": 0, "2xx": 0, "non_2xx": 0, "conn_err": 0, "latencies": []}
        for i in range(duration)
    }
    pods = Counter()

    for res in results:
        expected_start, actual_start, actual_end, status, pod = res
        sec_sent = int(actual_start - base_time)
        sec_completed = int(actual_end - base_time)

        if 0 <= sec_sent < duration:
            per_second_stats[sec_sent]["actual_sent"] += 1

        if 0 <= sec_completed < duration:
            if 200 <= status < 300:
                per_second_stats[sec_completed]["2xx"] += 1
                latency_ms = (actual_end - expected_start) * 1000
                per_second_stats[sec_completed]["latencies"].append(latency_ms)
                if pod and sec_completed >= duration - 20:
                    pods[pod] += 1
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

        if step_name != "Прогрів" and sec >= (duration - 20):
            step_achieved_rps_list.append(st['2xx'])

    avg_achieved = sum(step_achieved_rps_list) / len(step_achieved_rps_list) if step_achieved_rps_list else 0
    if step_name != "Прогрів":
        print(
            f"-> Середня досягнута інтенсивність на сходинці (останні 20с): {avg_achieved:.2f} RPS (Поріг 90%: {0.9 * target_rps:.2f} RPS)")
        if pods:
            per_pod_rps = {p: c / 20 for p, c in sorted(pods.items())}
            avg_pod = sum(per_pod_rps.values()) / len(per_pod_rps)
            print("-> RPS по подах (2xx, останні 20с): " +
                  ", ".join(f"{p}: {v:.1f}" for p, v in per_pod_rps.items()) +
                  f" | I = max/середнє = {max(per_pod_rps.values()) / avg_pod:.3f}")

    return avg_achieved

async def run_profile(segments, valid_ids, csv_path=None):
    duration = sum(d for d, _ in segments)
    sec_rate, sec_seg = [], []
    for k, (d, r) in enumerate(segments):
        sec_rate += [r] * d
        sec_seg += [k] * d

    print(f"\n{'=' * 80}")
    print("Профіль: " + ", ".join(f"[{d} с, {r} RPS]" for d, r in segments) + f" | Разом: {duration} с")
    print(f"{'=' * 80}")

    queue = asyncio.Queue()
    stop_event = asyncio.Event()
    results = []

    async def worker():
        while not stop_event.is_set():
            connector = aiohttp.TCPConnector(limit=1)
            async with aiohttp.ClientSession(connector=connector, timeout=TIMEOUT) as session:
                done = 0
                while done < REQUESTS_PER_CONNECTION and not stop_event.is_set():
                    try:
                        expected_start = await asyncio.wait_for(queue.get(), timeout=0.1)
                    except asyncio.TimeoutError:
                        continue
                    record_id = random.choice(valid_ids)
                    actual_start = time.time()
                    status = 0
                    pod = None
                    try:
                        async with session.get(URL_TEMPLATE.format(record_id)) as response:
                            await response.read()
                            status = response.status
                            pod = response.headers.get("X-Pod")
                    except asyncio.TimeoutError:
                        status = 408
                    except Exception:
                        status = 0
                    actual_end = time.time()
                    results.append((expected_start, actual_start, actual_end, status, pod))
                    queue.task_done()
                    done += 1

    workers = [asyncio.create_task(worker()) for _ in range(NUM_CONNECTIONS)]

    base_time = time.time()
    print(f"Початок профілю (unix, для звірки з Prometheus): {base_time:.3f}")

    offset = 0
    for d, r in segments:
        seg_start = base_time + offset
        for i in range(int(r * d)):
            expected_start = seg_start + i / r
            now = time.time()
            if expected_start > now:
                await asyncio.sleep(expected_start - now)
            queue.put_nowait(expected_start)
        offset += d
        wait = base_time + offset - time.time()
        if wait > 0:
            await asyncio.sleep(wait)

    stop_event.set()
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    stats = {i: {"sent": 0, "2xx": 0, "non_2xx": 0, "conn_err": 0, "lat": []} for i in range(duration)}
    pods = {k: Counter() for k in range(len(segments))}
    for expected_start, actual_start, actual_end, status, pod in results:
        ss = int(actual_start - base_time)
        sc = int(actual_end - base_time)
        if 0 <= ss < duration:
            stats[ss]["sent"] += 1
        if 0 <= sc < duration:
            if 200 <= status < 300:
                stats[sc]["2xx"] += 1
                stats[sc]["lat"].append((actual_end - expected_start) * 1000)
                if pod:
                    pods[sec_seg[sc]][pod] += 1
            elif status == 0:
                stats[sc]["conn_err"] += 1
            else:
                stats[sc]["non_2xx"] += 1

    print("Секунда | Відрізок | Задано | Відправлено | Досягнуто(2xx) | Не 2xx | Помилки з'єдн. | p50 (ms) | p95 (ms) | p99 (ms)")
    rows = []
    for sec in range(duration):
        st = stats[sec]
        lats = sorted(st["lat"])
        p50 = lats[int(len(lats) * 0.50)] if lats else 0
        p95 = lats[int(len(lats) * 0.95)] if lats else 0
        p99 = lats[int(len(lats) * 0.99)] if lats else 0
        rows.append((sec + 1, sec_seg[sec] + 1, sec_rate[sec], st["sent"], st["2xx"], st["non_2xx"], st["conn_err"], p50, p95, p99))
        print(f"{sec + 1:7d} | {sec_seg[sec] + 1:8d} | {sec_rate[sec]:6d} | {st['sent']:11d} | {st['2xx']:14d} | "
              f"{st['non_2xx']:6d} | {st['conn_err']:14d} | {p50:8.1f} | {p95:8.1f} | {p99:8.1f}")

    print("\nПідсумок за відрізками (повністю):")
    t0 = 0
    for k, (d, r) in enumerate(segments):
        seg = rows[t0:t0 + d]
        t0 += d
        ach = [x[4] for x in seg]
        p99s = sorted(x[9] for x in seg)
        tail = f"{k + 1}: {d:3d} с, задано {r:5d} RPS | досягнуто середнє {sum(ach) / len(ach):7.2f} (min {min(ach)}, max {max(ach)}) | " \
               f"p99 мед {p99s[len(p99s) // 2]:7.1f} макс {p99s[-1]:7.1f} мс | не-2xx {sum(x[5] for x in seg)} | пом.з'єдн {sum(x[6] for x in seg)}"
        print("  відрізок " + tail)
        if pods[k]:
            tot = sum(pods[k].values())
            print("     частка 2xx по подах: " + ", ".join(f"{p}: {c / tot:.3f}" for p, c in sorted(pods[k].items())))

    if csv_path:
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("unix_start,sec,segment,expected,sent,ok_2xx,non_2xx,conn_err,p50_ms,p95_ms,p99_ms\n")
            for x in rows:
                f.write(f"{base_time:.3f},{x[0]},{x[1]},{x[2]},{x[3]},{x[4]},{x[5]},{x[6]},{x[7]:.1f},{x[8]:.1f},{x[9]:.1f}\n")
        print(f"CSV збережено: {csv_path}")
    return rows


def build_profile(x1, xr, k):
    low = round(0.3 * x1)
    variant_level = k * x1
    cap = 0.9 * xr
    spike = round(min(variant_level, cap))
    print(f"X(1) = {x1}, X(R) = {xr}")
    print(f"0.3*X(1) = {low}; рівень за варіантом {k}*X(1) = {variant_level:.1f}; 0.9*X(R) = {cap:.1f}"
          f" -> рівень стрибка = {spike} ({'за варіантом' if variant_level <= cap else 'обмежено 0.9*X(R)'})")
    return [(30, low), (60, spike), (90, low)]


def silence_winerror_10054(loop, context):
    exc = context.get('exception')
    if isinstance(exc, ConnectionResetError) or (isinstance(exc, OSError) and exc.errno == 10054):
        return
    loop.default_exception_handler(context)


async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", action="store_true", help="виконати профіль кроку 10 замість ступінчастого прогону")
    ap.add_argument("--x1", type=float, help="X(1) з кроку 7, RPS")
    ap.add_argument("--xr", type=float, help="X(R) з кроку 7, RPS")
    ap.add_argument("--k", type=float, default=2.0, help="множник рівня за варіантом (варіант 17: 2 · X(1))")
    ap.add_argument("--csv", default="profile_run.csv")
    ap.add_argument("--no-warmup", action="store_true", help="без прогріву 100 RPS (для прогону з HPA)")
    args = ap.parse_args()

    loop = asyncio.get_running_loop()
    loop.set_exception_handler(silence_winerror_10054)

    try:
        with open("ids.txt", "r") as f:
            valid_ids = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Файл ids.txt не знайдено. Спочатку запустіть populate.py")
        return

    if not (args.profile and args.no_warmup):
        await run_step(target_rps=100, duration=10, valid_ids=valid_ids, step_name="Прогрів")

    if args.profile:
        if not args.x1 or not args.xr:
            print("Для --profile потрібні --x1 і --xr (значення з кроку 7).")
            return
        if not args.no_warmup:
            await asyncio.sleep(5)
        await run_profile(build_profile(args.x1, args.xr, args.k), valid_ids, args.csv)
        await asyncio.sleep(0.250)
        return

    current_rps = 200
    consecutive_fails = 0

    while True:
        avg_achieved = await run_step(
            target_rps=current_rps,
            duration=30,
            valid_ids=valid_ids,
            step_name=f"Сходинка {current_rps} RPS"
        )

        if avg_achieved < 0.9 * current_rps:
            consecutive_fails += 1
            print(f"[!] УВАГА: Сервер не справляється (Спроба {consecutive_fails}/2).")
        else:
            consecutive_fails = 0

        if consecutive_fails >= 2:
            print("\n[!] ТЕСТ ЗУПИНЕНО: На двох сходинках поспіль досягнута інтенсивність нижча за 0.9 від заданої.")
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
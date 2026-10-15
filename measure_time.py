import time
import subprocess
import requests

def measure():
    subprocess.run(["docker", "compose", "down", "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Запускаємо стенд...")
    start_time = time.time()
    subprocess.run(["docker", "compose", "up", "-d"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while True:
        try:
            response = requests.get("http://localhost/healthz", timeout=1)
            if response.status_code == 200:
                elapsed = time.time() - start_time
                print(f"Готово! Час: {elapsed:.2f} секунд")
                return elapsed
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.1)

if __name__ == "__main__":
    results = []
    for i in range(3):
        print(f"Спроба {i + 1}")
        results.append(measure())

    results.sort()
    print(f"\nУсі результати: {results}")
    print(f"Медіанний час: {results[1]:.2f} секунд")
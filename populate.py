import requests
import datetime

url = "http://localhost/dispensary"
created_ids = []

for i in range(1, 101):
    payload = {
        "patient_code": f"PAT-{i:04d}",
        "accounting_group": f"Group {i%3 + 1}",
        "registration_date": datetime.date.today().isoformat(),
        "periodicity_months": (i % 24) + 1,
        "last_examination_date": datetime.date.today().isoformat()
    }
    resp = requests.post(url, json=payload)
    if resp.status_code == 201:
        created_ids.append(resp.json()["id"])
    else:
        print(f"Помилка створення {i}: {resp.status_code} - {resp.text}")

with open("ids.txt", "w") as f:
    for uid in created_ids:
        f.write(f"{uid}\n")

print(f"100 записів успішно створено! ID збережено у ids.txt")
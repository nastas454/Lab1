import matplotlib.pyplot as plt

rps_steps = [200, 400, 600, 800, 1000]
metric_n1 = [10, 10, 10, 10, 10]
metric_n4 = [10, 20, 30, 40, 40]

plt.figure(figsize=(10, 6))

plt.plot(rps_steps, metric_n1, marker='o', linestyle='-', color='blue', label='N = 1', markersize=8)
plt.plot(rps_steps, metric_n4, marker='s', linestyle='-', color='green', label='N = 4', markersize=8)

plt.title('Залежність кількості активних з\'єднань БД від інтенсивності')
plt.xlabel('Задана інтенсивність (RPS)')
plt.ylabel('Активні з\'єднання (pg_stat_activity_count)')
plt.xticks(rps_steps)
plt.legend()
plt.grid(True, linestyle='--', alpha=0.7)

plt.axhline(y=10, color='blue', linestyle=':', alpha=0.5)
plt.axhline(y=40, color='green', linestyle=':', alpha=0.5)
plt.text(200, 11, 'Ліміт пулу (N=1)', color='blue', fontsize=9)
plt.text(200, 41, 'Ліміт пулу (N=4)', color='green', fontsize=9)

plt.tight_layout()
plt.savefig('m2_metric_chart.png', dpi=150)
print("Діаграму успішно збережено як m2_metric_chart.png")
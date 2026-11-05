import numpy as np
import matplotlib.pyplot as plt

N_measured = np.array([1, 2, 3, 4])
X_measured = np.array([210.80, 399.93, 598.53, 609.00])
X_errors = np.array([117, 6, 7, 572])

lam = X_measured[0]

N_calc = N_measured[1:]
X_calc = X_measured[1:]

C = X_calc / lam

y = (N_calc / C) - 1
u = N_calc - 1
v = N_calc * (N_calc - 1)

sum_u2 = np.sum(u**2)
sum_v2 = np.sum(v**2)
sum_uv = np.sum(u * v)
sum_uy = np.sum(u * y)
sum_vy = np.sum(v * y)

print("--- Проміжні розрахунки МНК ---")
print(f"C(N): {C}")
print(f"y(N): {y}")
print(f"u(N): {u}")
print(f"v(N): {v}")
print(f"Сума u^2: {sum_u2}")
print(f"Сума v^2: {sum_v2}")
print(f"Сума u*v: {sum_uv}")
print(f"Сума u*y: {sum_uy:.4f}")
print(f"Сума v*y: {sum_vy:.4f}\n")

det = (sum_u2 * sum_v2) - (sum_uv**2)
sigma = ((sum_uy * sum_v2) - (sum_vy * sum_uv)) / det
kappa = ((sum_u2 * sum_vy) - (sum_uv * sum_uy)) / det

print(f"Початкова оцінка МНК: σ = {sigma:.4f}, κ = {kappa:.4f}")

if sigma < 0:
    print("Оскільки σ < 0, прирівнюємо σ = 0 і перераховуємо κ (κ = Σvy / Σv^2):")
    sigma = 0.0
    kappa = sum_vy / sum_v2

if kappa > 0:
    N_star = np.sqrt((1 - sigma) / kappa)
else:
    N_star = float('inf')

print(f"\n--- Фінальні результати USL ---")
print(f"λ (X(1)) = {lam:.2f}")
print(f"σ (Конкуренція) = {sigma:.4f}")
print(f"κ (Узгодженість) = {kappa:.4f}")
print(f"Оптимальна кількість екземплярів N* = {N_star:.2f}")

def usl_model(n, s, k):
    return (lam * n) / (1 + s * (n - 1) + k * n * (n - 1))

N_smooth = np.linspace(1, 8, 100)
X_usl = usl_model(N_smooth, sigma, kappa)
X_linear = lam * N_smooth
plt.figure(figsize=(10, 6))

plt.plot(N_smooth, X_linear, 'g--', label=r"Ідеальне масштабування ($\lambda N$)", alpha=0.6)
plt.plot(N_smooth, X_usl, 'b-', label=rf"Крива USL МНК ($\sigma$={sigma:.4f}, $\kappa$={kappa:.4f})", linewidth=2)
plt.errorbar(N_measured, X_measured, yerr=X_errors, fmt='ro', label="Виміряне $X(N)$ з розкидом", capsize=5)

if N_star != float('inf') and N_star < N_smooth[-1]:
    X_max = usl_model(N_star, sigma, kappa)
    plt.plot(N_star, X_max, 'm*', markersize=12, label=f"Пік $N^*$ ({N_star:.2f} екз.)")

plt.xlabel("Кількість екземплярів (N)")
plt.ylabel("Пропускна здатність (RPS)")
plt.title("Аналіз масштабованості системи (USL) за МНК")
plt.legend()
plt.grid(True, linestyle=':', alpha=0.7)

plt.savefig("usl_chart.png", dpi=150)
print("\nГрафік успішно збережено як usl_chart.png")
plt.show()
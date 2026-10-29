import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

N_measured = np.array([1, 2, 3, 4])
X_measured = np.array([210.80, 399.93, 598.53, 609.00])
X_errors = np.array([58, 3, 55, 280])
lam = X_measured[0]

def usl_model(n, sigma, kappa):
    return (lam * n) / (1 + sigma * (n - 1) + kappa * n * (n - 1))

popt, _ = curve_fit(usl_model, N_measured, X_measured, bounds=(0, 1))
sigma, kappa = popt

if kappa > 0:
    N_star = np.sqrt((1 - sigma) / kappa)
else:
    N_star = float('inf')

print(f"--- Результати розрахунку USL ---")
print(f"λ (X(1)) = {lam:.2f}")
print(f"σ (Конкуренція) = {sigma:.4f}")
print(f"κ (Узгодженість) = {kappa:.4f}")
print(f"Оптимальна кількість екземплярів N* = {N_star:.2f}")

N_smooth = np.linspace(1, max(7, int(N_star) + 2), 100)
X_usl = usl_model(N_smooth, sigma, kappa)
X_linear = lam * N_smooth

plt.figure(figsize=(10, 6))
plt.plot(N_smooth, X_linear, 'g--', label=r"Ідеальне масштабування ($\lambda N$)", alpha=0.6)
plt.plot(N_smooth, X_usl, 'b-', label=rf"Крива USL ($\sigma$={sigma:.4f}, $\kappa$={kappa:.4f})", linewidth=2)
plt.errorbar(N_measured, X_measured, yerr=X_errors, fmt='ro', label="Виміряне $X(N)$ з розкидом", capsize=5)

if N_star != float('inf') and N_star < N_smooth[-1]:
    X_max = usl_model(N_star, sigma, kappa)
    plt.plot(N_star, X_max, 'm*', markersize=12, label=f"Пік $N^*$ ({N_star:.1f} екз.)")

plt.xlabel("Кількість екземплярів (N)")
plt.ylabel("Пропускна здатність (RPS)")
plt.title("Аналіз масштабованості системи (USL)")
plt.legend()
plt.grid(True, linestyle=':', alpha=0.7)

plt.savefig("usl_chart.png", dpi=150)
print("\nГрафік успішно збережено як usl_chart.png")
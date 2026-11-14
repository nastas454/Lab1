import numpy as np
import matplotlib.pyplot as plt

K8S_DATA = {
    1: (199.90, 145.0, 244.0),
    2: (200.00, 197.0, 202.0),
    3: (567.65, 414.0, 636.0),
    5: (746.05, 613.0, 871.0),
}

COMPOSE_DATA = {
    1: (200.00, 192.0, 208.0),
    2: (398.50, 382.0, 412.0),
    3: (585.00, 545.0, 615.0),
    5: (790.00, 735.0, 835.0),
}

def fit_usl(data_dict):
    ns = np.array(sorted(data_dict.keys()), dtype=float)
    xs = np.array([data_dict[n][0] for n in ns], dtype=float)
    x1 = xs[0]
    cn = xs / x1

    ns_fit = ns[1:]
    cn_fit = cn[1:]
    y = ns_fit / cn_fit - 1.0

    u = ns_fit - 1.0
    v = ns_fit * (ns_fit - 1.0)
    X_mat = np.column_stack([u, v])
    sigma, kappa = np.linalg.lstsq(X_mat, y, rcond=None)[0]

    if kappa < 0:
        kappa = 0.0
        sigma = max(0.0, float(np.sum(u * y) / np.sum(u ** 2)))
    if sigma < 0:
        sigma = 0.0
        kappa = max(0.0, float(np.sum(v * y) / np.sum(v ** 2)))

    n_star = np.sqrt((1.0 - sigma) / kappa) if kappa > 0 else float("inf")
    return sigma, kappa, n_star, ns, cn

s_k8s, k_k8s, nstar_k8s, ns_k, cn_k = fit_usl(K8S_DATA)
s_cmp, k_cmp, nstar_cmp, ns_c, cn_c = fit_usl(COMPOSE_DATA)

print("=" * 75)
print("РЕЗУЛЬТАТИ КРОКУ 9 (Універсальний закон масштабованості)")
print("=" * 75)
nstar_k_str = f"{nstar_k8s:.2f}" if np.isfinite(nstar_k8s) else "∞ (монотонно зростає)"
nstar_c_str = f"{nstar_cmp:.2f}" if np.isfinite(nstar_cmp) else "∞ (монотонно зростає)"
print(f"Kubernetes (ЛР3)     : σ = {s_k8s:.5f}, κ = {k_k8s:.5f}, N* = {nstar_k_str}")
print(f"Docker Compose (ЛР2) : σ = {s_cmp:.5f}, κ = {k_cmp:.5f}, N* = {nstar_c_str}")

n_grid = np.linspace(1.0, 5.3, 200)
usl_c = lambda N, s, k: N / (1.0 + s * (N - 1.0) + k * N * (N - 1.0))

plt.figure(figsize=(9.5, 5.8), dpi=150)

x1_k = K8S_DATA[1][0]
err_low_k = [cn_k[i] - K8S_DATA[int(n)][1] / x1_k for i, n in enumerate(ns_k)]
err_high_k = [K8S_DATA[int(n)][2] / x1_k - cn_k[i] for i, n in enumerate(ns_k)]
plt.errorbar(
    ns_k - 0.04, cn_k, yerr=[err_low_k, err_high_k],
    fmt="o", color="#1f77b4", ecolor="#1f77b4", elinewidth=1.5, capsize=5, markersize=7,
    label="Kubernetes: експериментальні C(N) з розкидом"
)
plt.plot(
    n_grid, usl_c(n_grid, s_k8s, k_k8s), "-", color="#1f77b4", linewidth=2.2,
    label=f"Kubernetes: крива USL (σ={s_k8s:.4f}, κ={k_k8s:.4f})"
)

x1_c = COMPOSE_DATA[1][0]
err_low_c = [cn_c[i] - COMPOSE_DATA[int(n)][1] / x1_c for i, n in enumerate(ns_c)]
err_high_c = [COMPOSE_DATA[int(n)][2] / x1_c - cn_c[i] for i, n in enumerate(ns_c)]
plt.errorbar(
    ns_c + 0.04, cn_c, yerr=[err_low_c, err_high_c],
    fmt="s", color="#ff7f0e", ecolor="#ff7f0e", elinewidth=1.5, capsize=5, markersize=7,
    label="Docker Compose (ЛР2): експериментальні C(N) з розкидом"
)
plt.plot(
    n_grid, usl_c(n_grid, s_cmp, k_cmp), "--", color="#ff7f0e", linewidth=2.2,
    label=f"Docker Compose (ЛР2): крива USL (σ={s_cmp:.4f}, κ={k_cmp:.4f})"
)

plt.plot(n_grid, n_grid, ":", color="gray", linewidth=1.5, label="Ідеальне масштабування C(N) = N")

plt.title("Порівняння відносної пропускної здатності C(N) та кривих USL: Kubernetes vs Docker Compose", fontsize=11, pad=12)
plt.xlabel("Кількість реплік N", fontsize=10)
plt.ylabel("Відносна пропускна здатність C(N) = X(N) / X(1)", fontsize=10)
plt.xticks([1, 2, 3, 4, 5])
plt.ylim(0, 5.5)
plt.grid(True, linestyle=":", alpha=0.6)
plt.legend(loc="upper left", fontsize=9)
plt.tight_layout()
plt.savefig("step9_usl_comparison.png")
print("[OK] Діаграму збережено у файл: step9_usl_comparison.png")
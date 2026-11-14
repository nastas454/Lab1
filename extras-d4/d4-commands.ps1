# Д4. Кожен з двох прогонів: ЗАВЖДИ на 5 готових репліках, навантаження на рівні, що стабільно тримається (напр. стрибок з кроку 10)
kubectl scale deployment/web --replicas=5
kubectl rollout status deployment/web
kubectl get pods -l app=web -o wide                      # скільки подів на кожному worker

# --- Прогін А: З PodDisruptionBudget ---
kubectl apply -f extras-d4/web-pdb.yaml
# запустити генератор; через ~30 с після початку:
kubectl drain kind-worker2 --ignore-daemonsets --delete-emptydir-data
# фіксувати: kube_deployment_status_replicas_ready{deployment="web"}, помилки, p99
kubectl uncordon kind-worker2
kubectl wait --for=condition=available deployment/web --timeout=120s
kubectl get pods -l app=web                              # дочекатися 5/5 Running і Ready

# --- Прогін Б: БЕЗ PodDisruptionBudget ---
kubectl delete -f extras-d4/web-pdb.yaml
# повторити те саме навантаження і drain того ж вузла
kubectl drain kind-worker2 --ignore-daemonsets --delete-emptydir-data
kubectl uncordon kind-worker2

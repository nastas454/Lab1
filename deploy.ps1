$ErrorActionPreference = "Stop"

kind create cluster --config kind-config.yaml
kubectl label node kind-control-plane role=infra --overwrite
docker build -t lab-web:latest .
kind load docker-image lab-web:latest

kubectl create secret generic db-secret --from-env-file=.env

kubectl delete job db-migrate --ignore-not-found
kubectl apply -f k8s/
kubectl rollout status statefulset/db --timeout=180s
kubectl wait --for=condition=complete job/db-migrate --timeout=180s
kubectl rollout status deployment/web --timeout=180s

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm repo update
helm upgrade --install metrics-server metrics-server/metrics-server -n kube-system `
  --set "args={--kubelet-insecure-tls}" -f monitoring/metrics-server-values.yaml
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack -f monitoring/prom-values.yaml
kubectl rollout status deployment/prometheus-kube-state-metrics --timeout=180s
kubectl apply -f monitoring/web-servicemonitor.yaml
helm upgrade --install pg-exporter prometheus-community/prometheus-postgres-exporter `
  -f monitoring/pg-exporter-values.yaml

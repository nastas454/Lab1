kind create cluster --config kind-config.yaml
kubectl label node kind-control-plane role=infra
docker build -t lab-web:latest .
kind load docker-image lab-web:latest
kubectl create secret generic db-secret --from-env-file=.env
kubectl apply -f k8s/
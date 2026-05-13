# ELK stack — log aggregation for FinTech platform

Deployed in the `logging` namespace alongside the application's `default` namespace.

## Components

| Component | Pods | Service | Access |
|-----------|------|---------|--------|
| Elasticsearch 8.13.4 | 1 | ClusterIP `elasticsearch:9200` | Internal only |
| Logstash 8.13.4 | 1 | ClusterIP `logstash:5044` | Internal only |
| Kibana 8.13.4 | 1 | NodePort `30601` | http://192.168.49.2:30601 |

## Apply

```bash
kubectl apply -f infra/k8s/40-logging/
```

## Verify

```bash
kubectl get pods -n logging
kubectl get svc -n logging
```

## Access Kibana

http://192.168.49.2:30601

## Resource budget (Path B reduced)

- Elasticsearch: 512M heap, 1Gi limit
- Logstash: 256M heap, 512Mi limit
- Kibana: 384Mi limit
- Total: ~1.9Gi RAM

Fits in current 4GB minikube allocation alongside Postgres + 3 services.
Production deployment would use StatefulSet + PVCs + xpack.security + multi-node ES.

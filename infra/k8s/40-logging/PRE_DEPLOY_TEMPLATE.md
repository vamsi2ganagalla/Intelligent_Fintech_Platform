# Pre-deploy: Elasticsearch Index Template

Filebeat is configured with `setup.template.enabled: false`, so the index
template must be created in ES **before** Filebeat first connects to it.
This template establishes `fintech-logs-*` as a data-stream pattern.

Run AFTER Elasticsearch is up and BEFORE applying `40-filebeat.yaml`:

```bash
kubectl exec -n logging \
  $(kubectl get pods -n logging -l app=elasticsearch -o jsonpath='{.items[0].metadata.name}') \
  -- curl -s -X PUT "http://localhost:9200/_index_template/fintech-logs" \
     -H "Content-Type: application/json" \
     -d '{
       "index_patterns": ["fintech-logs","fintech-logs-*"],
       "data_stream": {},
       "priority": 500,
       "template": {
         "settings": {
           "number_of_shards": 1,
           "number_of_replicas": 0
         }
       }
     }'
```

Expected response: `{"acknowledged":true}`

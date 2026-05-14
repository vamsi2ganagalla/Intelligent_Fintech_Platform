# Day 6 Decisions Log — ELK + JSON Logging + Correlation IDs

**Date:** 2026-05-14  
**Tag:** day-6-complete  
**Phases:** 6.1 – 6.9

---

## Architecture Decisions

### D1: Path B — No Logstash (Filebeat → ES Direct)
**Decision:** Ship logs Filebeat → Elasticsearch directly, skipping Logstash.  
**Reason:** minikube cluster capped at 4GB RAM (resize requires cluster delete, destroying
Postgres data). Logstash adds ~512Mi overhead with no benefit at academic scale.  
**Trade-off:** Less pipeline flexibility (no grok filters, no conditional routing).
For FinTech production: Logstash would add field normalization and PCI-DSS audit routing.

### D2: Single-node Elasticsearch, emptyDir volumes
**Decision:** `discovery.type: single-node`, no persistence (emptyDir).  
**Reason:** Academic scope. Single-node avoids split-brain config complexity.
emptyDir avoids PVC provisioner setup.  
**Trade-off:** Logs lost on ES pod restart. Production: 3-node cluster + PVC.

### D3: Profile-aware logback (local=text, prod=JSON)
**Decision:** `logback-spring.xml` with `<springProfile name="prod">` wrapping LogstashEncoder.  
**Reason:** IntelliJ readability requires human-readable text locally. K8s pods get
JSON for Filebeat ingestion. `SPRING_PROFILES_ACTIVE=prod` in ConfigMap activates JSON.  
**Lesson:** Spring nanosecond `@timestamp` (9 digits) conflicts with ES millisecond
mapping. Fix: `overwrite_keys: false` in Filebeat `decode_json_fields` processor.

### D4: Custom CorrelationIdFilter (not Spring Cloud Sleuth)
**Decision:** Hand-rolled `OncePerRequestFilter` at `@Order(-100)`.  
**Reason:** Sleuth adds significant dependency weight and opinionated trace format.
Our filter is ~50 lines, fully understood, and produces exactly the fields Kibana needs.  
**Implementation:** UUID per request, reuses `X-Correlation-Id` if present (for
cross-service propagation). MDC cleared in `finally` block (thread-pool safety).  
**Verified:** correlationId present in controller, service, and exception handler log
lines for every request.

### D5: RestTemplate interceptor for cross-service propagation
**Decision:** `CorrelationIdInterceptor implements ClientHttpRequestInterceptor`,
wired into a `@Bean RestTemplate`.  
**Reason:** Any future inter-service call automatically forwards `X-Correlation-Id`.
No current callers exist, but the infrastructure is in place.  
**Fallback chain:** MDC → servlet request header → sentinel `"no-correlation-id"`.

### D6: Filebeat data stream template pre-creation
**Decision:** Manually `PUT /_index_template/fintech-logs` before Filebeat connects,
with `"data_stream": {}` and `"priority": 500`. Set `setup.template.enabled: false`
in Filebeat config.  
**Reason:** Filebeat 8.x unconditionally attempts to create a data stream on connect.
Without a pre-existing template with `data_stream: {}`, ES returns 400. Filebeat's
own template setup does not include the data_stream declaration.  
**Lesson:** `setup.template.overwrite: true` causes Filebeat to replace any manually
created template with its own (which lacks `data_stream: {}`). Must disable template
setup entirely.

### D7: decode_json_fields with conditional when-regexp
**Decision:** Use `decode_json_fields` processor (not `json.*` input-level keys)
with `when: {regexp: {message: "^\s*\{"}}` to parse Spring JSON selectively.  
**Reason:** `type: container` input does not support `json.*` keys in Filebeat 8.13.4
(silently ignored). `decode_json_fields` is the correct processor for this input type.
The `when` condition prevents Postgres plain-text lines from triggering failed parses.  
**Verified:** ES docs contain top-level `correlationId`, `service`, `level`, `logger`
fields. Full K8s metadata (`kubernetes.pod.name`, `kubernetes.container.name`,
`kubernetes.namespace`) present via `add_kubernetes_metadata` processor.

---

## Mistakes Logged (Day 6, mentor accountability)

| # | Phase | Mistake | Fix |
|---|-------|---------|-----|
| 8 | 6.1 | Kibana 384Mi container limit — OOM at 244MB Node.js heap | Bumped to 768Mi |
| 9 | 6.2 | Literal-string pom.xml edit broke on tab-indented auth-service pom | Rewrote with regex (indent-agnostic) |
| 10 | 6.1 | Logstash dropped after OOM — should have been Path B from start | Path B: Filebeat → ES direct |
| 11 | 6.3b | `spring-boot:run` piped to `head -30` killed before app started | Background process + poll loop |
| 12 | 6.3 | Template used Python `{{}}` escaping → literal `{{` in XML `customFields` | Replaced with `.replace("SERVICE_NAME_PLACEHOLDER", ...)` |
| 13 | 6.6 | Invented `filebeat.data_streams.auto_detect_enabled` — doesn't exist | Pre-create ES index template instead |
| 14 | 6.6 | `sed` multiline YAML replacement broke indentation → Filebeat crash loop | Python full-rewrite of configmap |
| 15 | 6.6 | `ignore_missing` key on `decode_json_fields` — doesn't exist | Removed; used only valid keys |

---

## Verification Evidence

### JSON logging in K8s pods
{"@timestamp":"2026-05-14T03:53:52.573Z","level":"INFO",
"message":"Started AuthServiceApplication in 20.716 seconds",
"logger":"com.fintech.auth.AuthServiceApplication","service":"auth-service"}

### CorrelationId end-to-end trace
Request `8603bf36-e35f-455a-a2fa-43b6c1a83b1c` in ES:
- `auth-service` | INFO | "Registration request received for email: e2e-verify@fintech.com"
- `auth-service` | INFO | "User registered: e2e-verify@fintech.com"
- `transaction-service` echoed same ID in `X-Correlation-Id` response header ✅

### Filebeat pipeline
- DaemonSet: 1/1 Running in `logging` namespace
- 26+ docs with `correlationId` field in ES
- Full K8s metadata: `kubernetes.pod.name`, `kubernetes.container.name`, `kubernetes.namespace`
- 3 Kibana saved searches: Auth Service Logs, Errors and Warnings, Trace by Correlation ID

---

## Deferred to Day 7+

- xpack.security for Elasticsearch (academic shortcut — no auth on ES)
- ES persistence via PVC (currently emptyDir — data lost on pod restart)
- Multi-node ES cluster
- Logstash pipeline (deferred in favour of Path B)
- `userEmail` MDC field (declared in logback, populated in Phase 6.4 filter
  only after JWT validation — needs SecurityContext wiring)
- message.keyword truncation (ES 32KB keyword limit — cosmetic, not functional)
- Asymmetric JWT RS256 + Vault → Day 7

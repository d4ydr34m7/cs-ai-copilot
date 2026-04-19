CRITICAL_DB_PRODUCTION = {
    "monitor_id": "839201A",
    "status": "Triggered",
    "title": "[CRITICAL] Oracle DB connection pool exhausted",
    "tags": [
        "env:production",
        "service:wire-to-core",
        "team:data-eng",
        "db:oracle-primary",
    ],
    "event_msg": (
        "java.sql.SQLRecoverableException: IO Error: The Network Adapter "
        "could not establish the connection."
    ),
    "timestamp": 1713369600,
}

API_TIMEOUT_STAGING = {
    "monitor_id": "monitor-88421",
    "status": "Triggered",
    "title": "[WARN] Payments API latency above threshold",
    "tags": [
        "env:staging",
        "service:payments-api",
        "team:backend",
    ],
    "event_msg": (
        "upstream request failed: context deadline exceeded after 30s "
        "calling POST /v1/transfers"
    ),
    "timestamp": 1713370200,
}

INFRA_CPU_SPIKE = {
    "monitor_id": "host-k8s-node-07",
    "status": "Triggered",
    "title": "[WARN] Kubernetes node CPU sustained high utilization",
    "tags": [
        "env:production",
        "kube_cluster:prod-use1",
        "team:infra",
    ],
    "event_msg": (
        "avg(cpu.utilization) > 92% for 15m on node ip-10-0-47-12.ec2.internal"
    ),
    "timestamp": 1713370800,
}

NOISY_LOW_SEVERITY = {
    "monitor_id": "dd-synthetics-991",
    "status": "Recovered",
    "title": "[OK] Synthetic check recovered: marketing homepage",
    "tags": [
        "env:staging",
        "check_type:synthetic",
        "team:web",
    ],
    "event_msg": "Check passed after 2 transient failures; no action required.",
    "timestamp": 1713371400,
}

VALID_LOG = """2024-04-01 thread #incident
oncall: checking payments-api — seeing timeouts
error log: connection refused to payments-api on port 5432
action: we restarted payments-api and pool cleared
"""

VALID_MARKDOWN = """# Payments API outage

## Symptoms
- Timeouts and connection refused to payments-api

## Root Cause
The API pool exhausted connections during traffic spike.

## Resolution Steps
1. Restart payments-api pods
2. Verify health checks pass

## Affected Services
- payments-api
"""

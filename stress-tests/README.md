# Stress Testing with Artillery

This directory contains load/stress tests for the Arbitrage Dashboard API using [Artillery](https://artillery.io/).

## Quick Start

```bash
# Install dependencies
cd stress-tests
npm install

# Make sure the API server is running
# In another terminal: cd .. && python -m uvicorn api.main:app --reload

# Run a quick WebSocket test
npm run test:ws:quick

# Run a quick API test
npm run test:api:quick
```

## Test Configurations

### 1. WebSocket Load Test (`websocket-load.yml`)

Tests the `/ws/market_pairs` WebSocket endpoint with realistic user scenarios:

| Phase | Duration | Arrival Rate | Purpose |
|-------|----------|--------------|---------|
| Warm-up | 30s | 2/s | Gradual connection ramp-up |
| Normal load | 60s | 5/s | Simulate typical usage |
| Stress test | 30s | 15/s | Push connection limits |
| Spike test | 10s | 30/s | Sudden burst of connections |
| Cool-down | 20s | 2/s | Graceful wind-down |

**Scenarios:**
- **Basic WebSocket Connection (60%)**: Connect, receive broadcasts for 60s
- **Active Client with Ping (30%)**: Connect, send ping every 10s
- **Short-lived Connection (10%)**: Quick connect/disconnect (mobile users)

### 2. REST API Load Test (`api-load.yml`)

Tests the `/api/get_paired_markets` endpoint:

| Phase | Duration | Arrival Rate | Purpose |
|-------|----------|--------------|---------|
| Warm-up | 20s | 5/s | Initial ramp-up |
| Ramp-up | 30s | 10→30/s | Gradual increase |
| Sustained load | 60s | 30/s | Steady high load |
| Stress test | 30s | 50/s | Push limits |
| Spike | 10s | 100/s | Extreme burst |
| Cool-down | 20s | 5/s | Wind-down |

### 3. Advanced WebSocket Test (`websocket-advanced.yml`)

Uses custom processor (`processor.js`) for detailed metrics:
- Connection time tracking
- Message size monitoring
- Market pairs count validation
- Active opportunity counting

## Running Tests

### Quick Tests (for development)

```bash
# Quick WebSocket test (5 users, 3 each scenario)
npm run test:ws:quick

# Quick API test (20 users, 5 requests each)
npm run test:api:quick
```

### Full Tests

```bash
# Full WebSocket load test (~2.5 minutes)
npm run test:ws

# Full API load test (~3 minutes)
npm run test:api

# Run both
npm run test:all
```

### Generate HTML Reports

```bash
# WebSocket test with HTML report
npm run test:ws:report

# API test with HTML report
npm run test:api:report
```

Reports are saved to `reports/` directory.

## Understanding the Results

### Key Metrics to Watch

**For WebSocket tests:**
- `websocket.connect_time` - Time to establish connection
- `websocket.messages_received` - Broadcast messages per connection
- `vusers.failed` - Failed virtual users (connection errors)

**For API tests:**
- `http.response_time.p99` - 99th percentile response time
- `http.response_time.median` - Median response time
- `http.codes.200` - Successful responses
- `http.codes.5xx` - Server errors

### Performance Thresholds

Our tests enforce these thresholds:
- API p99 response time: < 500ms
- Error rate: < 1% (API), < 5% (WebSocket)

### Interpreting Results

```
All VUs finished. Total time: 170 seconds

--------------------------------
Summary report @ 12:34:56
--------------------------------

http.codes.200: .................................................. 1523
http.request_rate: ............................................... 9/sec
http.requests: ................................................... 1523
http.response_time:
  min: ........................................................... 12
  max: ........................................................... 487
  median: ........................................................ 45
  p95: ........................................................... 156
  p99: ........................................................... 312
```

**What to look for:**
- `p99 < 500ms` = Good API performance
- `http.codes.200` should match `http.requests` (no errors)
- Consistent `median` times (no degradation under load)

## Bottleneck Analysis

After running tests, check for:

1. **Database bottlenecks**
   - If p99 increases significantly under load
   - Check Supabase connection pool limits

2. **WebSocket connection limits**
   - If `vusers.failed` increases
   - Check OS file descriptor limits: `ulimit -n`

3. **Memory pressure**
   - Monitor server memory during tests
   - Watch for increasing response times over duration

## Custom Processor Functions

The `processor.js` file provides custom functions:

| Function | Purpose |
|----------|---------|
| `setupConnection` | Initialize connection tracking |
| `onConnectionOpen` | Record connection time |
| `processMarketPairsMessage` | Validate and count market pairs |
| `beforeRequest` / `afterResponse` | API request hooks |
| `generateThinkTime` | Realistic user think time |
| `logSummary` | Session summary logging |

## Troubleshooting

### "Connection refused" errors
```bash
# Make sure the API server is running
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### WebSocket connection failures
```bash
# Check if WebSocket endpoint is accessible
wscat -c ws://localhost:8000/ws/market_pairs
```

### High error rates
- Check server logs for errors
- Reduce arrival rate in test config
- Check database connection limits

## CI/CD Integration

Add to your CI pipeline:

```yaml
# .github/workflows/stress-test.yml
stress-test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - name: Start API server
      run: |
        python -m uvicorn api.main:app &
        sleep 5
    - name: Run stress tests
      run: |
        cd stress-tests
        npm install
        npm run test:api:quick
```

import assert from 'node:assert/strict'

const scenario = process.argv[2] || 'ready'
const expected = {
  ready: { mongodb: 'up', neo4j: 'up' },
  'mongo-down': { mongodb: 'down', neo4j: 'up' },
  'neo4j-down': { mongodb: 'up', neo4j: 'down' },
  'both-down': { mongodb: 'down', neo4j: 'down' },
}[scenario]
assert.ok(expected, 'Use ready, mongo-down, neo4j-down or both-down')

const base = process.env.CP_RUNTIME_BACKEND || 'http://127.0.0.1:8000'
const headers = { 'X-Request-ID': `runtime-${scenario}`, Origin: 'http://localhost:5173' }
const live = await fetch(`${base}/health/live`, { headers, signal: AbortSignal.timeout(10000) })
assert.equal(live.status, 200)
assert.deepEqual(await live.json(), { status: 'alive' })
const start = performance.now()
const ready = await fetch(`${base}/health/ready`, { headers, signal: AbortSignal.timeout(10000) })
const body = await ready.json()
assert.equal(ready.status, scenario === 'ready' ? 200 : 503)
assert.deepEqual(body.dependencies, expected)
assert.equal(ready.headers.get('X-Request-ID'), headers['X-Request-ID'])
assert.equal(ready.headers.get('Access-Control-Allow-Origin'), headers.Origin)
if (scenario !== 'ready') assert.equal(body.error.request_id, headers['X-Request-ID'])
const spec = await fetch(`${base}/openapi.json`).then((response) => response.json())
assert.equal(spec.info.title, 'CareerPilot')
const frontend = await fetch('http://127.0.0.1:5173/')
assert.equal(frontend.status, 200)
assert.match(await frontend.text(), /CareerPilot/)
const proxy = await fetch('http://127.0.0.1:5173/health/ready', { signal: AbortSignal.timeout(10000) })
assert.equal(proxy.status, ready.status)
assert.deepEqual((await proxy.json()).dependencies, expected)
console.log(JSON.stringify({ scenario, live: 200, readiness: ready.status, dependencies: expected,
  requestId: headers['X-Request-ID'], durationMs: Math.round(performance.now() - start),
  openapi: 'passed', frontend: 'served', viteProxy: 'passed' }))

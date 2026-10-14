import assert from 'node:assert/strict';

const baseUrl = (process.env.VITALGUARD_API_URL || 'https://vitalguard-risk-api.onrender.com').replace(/\/$/, '');
const timeoutMs = 20_000;
const coldStartTimeoutMs = 60_000;

async function request(path, options = {}, timeout = timeoutMs) {
  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    signal: AbortSignal.timeout(timeout),
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
  });
  const body = await response.text();
  let data;
  try {
    data = body ? JSON.parse(body) : null;
  } catch {
    data = body;
  }
  assert.ok(response.ok, `${options.method || 'GET'} ${path} returned ${response.status}: ${body}`);
  return { response, data };
}

async function main() {
  console.log(`Smoke-testing VitalGuard API: ${baseUrl}`);

  // Render free instances may need a cold start. Give health checks a longer
  // timeout and retry transient wake-up/network failures before failing the run.
  let health;
  let lastHealthError;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      ({ data: health } = await request('/health', {}, coldStartTimeoutMs));
      break;
    } catch (error) {
      lastHealthError = error;
      if (attempt < 3) {
        console.warn(`Health check attempt ${attempt}/3 did not complete; retrying in 5 seconds.`);
        await new Promise((resolve) => setTimeout(resolve, 5_000));
      }
    }
  }
  assert.ok(health, `Health endpoint failed after 3 attempts: ${lastHealthError}`);
  assert.equal(health.status, 'ok');
  assert.equal(health.demo_only, true);
  assert.equal(health.database?.status, 'ok', 'Health must confirm a reachable database');
  assert.ok(['sqlite', 'postgresql'].includes(health.database?.backend), 'Health must identify the active storage backend');
  if (health.database.backend === 'sqlite') {
    console.warn('⚠ Persistence readiness: API is using SQLite. On hosted ephemeral storage, records may not survive restart/redeploy; configure DATABASE_URL for PostgreSQL and verify durability.');
  } else {
    console.log('✓ PostgreSQL backend is active; restart/redeploy durability still requires a separate verification.');
  }
  console.log('✓ Health endpoint and storage-backend diagnostics');

  const { response: modelResponse, data: model } = await request('/api/v1/model/info');
  const expectedSecurityHeaders = {
    'x-content-type-options': 'nosniff',
    'x-frame-options': 'DENY',
    'referrer-policy': 'no-referrer',
    'permissions-policy': 'camera=(), microphone=(), geolocation=()',
    'cache-control': 'no-store',
  };
  for (const [header, expected] of Object.entries(expectedSecurityHeaders)) {
    assert.equal(modelResponse.headers.get(header), expected, 'Missing or incorrect security header: ' + header);
  }
  assert.ok(modelResponse.headers.get('x-request-id'), 'Each API response should include a request ID');
  console.log('✓ Baseline API security headers and request ID');
  assert.equal(model.demo_only, true);
  assert.equal(model.clinically_validated, false);
  assert.ok(Array.isArray(model.features) && model.features.length >= 7);
  console.log('✓ Model metadata and demo disclaimer');

  const { data: evaluation } = await request('/api/v1/model/evaluation');
  assert.equal(evaluation.demo_only, true);
  assert.equal(evaluation.clinically_validated, false);
  assert.equal(evaluation.sample_count, 3000);
  for (const metric of ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']) {
    assert.ok(evaluation.metrics[metric] >= 0 && evaluation.metrics[metric] <= 1, 'Invalid synthetic metric: ' + metric);
  }
  console.log('✓ Reproducible synthetic holdout evaluation');

  const { data: news2 } = await request('/api/v1/scores/news2', {
    method: 'POST',
    body: JSON.stringify({
      patient_id: 'SMOKE-NEWS2-' + Date.now(),
      respiratory_rate: 16,
      spo2: 98,
      systolic_bp: 120,
      heart_rate: 80,
      temperature: 37,
      consciousness: 'alert',
      supplemental_oxygen: false,
      spo2_scale: 1,
      scale2_authorized: false,
    }),
  });
  assert.equal(news2.demo_only, true);
  assert.equal(news2.clinically_validated_implementation, false);
  assert.equal(news2.total_score, 0);
  assert.equal(news2.parameter_scores.supplemental_oxygen, 0);
  console.log('✓ NEWS2 scoring demo endpoint and disclaimer');

  const scale2Denied = await fetch(baseUrl + '/api/v1/scores/news2', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      patient_id: 'SMOKE-NEWS2-DENIED', respiratory_rate: 16, spo2: 90,
      systolic_bp: 120, heart_rate: 80, temperature: 37, consciousness: 'alert',
      supplemental_oxygen: false, spo2_scale: 2, scale2_authorized: false,
    }),
    signal: AbortSignal.timeout(timeoutMs),
  });
  assert.equal(scale2Denied.status, 422, 'NEWS2 Scale 2 should require explicit authorization assertion');
  console.log('✓ NEWS2 Scale 2 authorization gate');

  const preflight = await fetch(`${baseUrl}/api/v1/risk/predict`, {
    method: 'OPTIONS',
    headers: {
      Origin: 'https://vitalguard-ai-g215.onrender.com',
      'Access-Control-Request-Method': 'POST',
      'Access-Control-Request-Headers': 'authorization,content-type',
    },
    signal: AbortSignal.timeout(timeoutMs),
  });
  assert.ok(preflight.ok, `CORS preflight returned ${preflight.status}`);
  assert.equal(
    preflight.headers.get('access-control-allow-origin'),
    'https://vitalguard-ai-g215.onrender.com',
    'CORS must allow the deployed frontend origin',
  );
  const allowedHeaders = (preflight.headers.get('access-control-allow-headers') || '')
    .toLowerCase()
    .split(',')
    .map((header) => header.trim());
  assert.ok(allowedHeaders.includes('authorization'), 'CORS must allow Authorization for authenticated browser requests');
  assert.ok(allowedHeaders.includes('content-type'), 'CORS must allow Content-Type for JSON requests');
  console.log('✓ Frontend CORS origin and requested headers');

  // Use fictional observations and a unique demo identifier so this test never
  // touches a real patient record. The API intentionally persists demo outputs.
  const patientId = `SMOKE-${Date.now()}`;
  const { data: prediction } = await request('/api/v1/risk/predict', {
    method: 'POST',
    body: JSON.stringify({
      patient_id: patientId,
      age: 58,
      heart_rate: 82,
      spo2: 98,
      systolic_bp: 122,
      diastolic_bp: 78,
      temperature: 37,
      respiratory_rate: 16,
    }),
  });
  assert.equal(prediction.patient_id, patientId);
  assert.equal(prediction.demo_only, true);
  assert.ok(Number.isInteger(prediction.risk_score) && prediction.risk_score >= 0 && prediction.risk_score <= 100);
  assert.ok(['low', 'moderate', 'high', 'critical'].includes(prediction.risk_level));
  assert.ok(prediction.observation_id > 0);
  assert.ok(prediction.created_at);
  console.log('✓ Prediction response and validation');

  const { data: explanation } = await request('/api/v1/risk/explain', {
    method: 'POST',
    body: JSON.stringify({
      patient_id: patientId, age: 58, heart_rate: 82, spo2: 98,
      systolic_bp: 122, diastolic_bp: 78, temperature: 37, respiratory_rate: 16,
    }),
  });
  assert.equal(explanation.demo_only, true);
  assert.equal(explanation.model_version, prediction.model_version);
  assert.equal(explanation.contributions.length, 7);
  assert.ok(explanation.caveat.includes('not causal'));
  console.log('✓ Model contribution endpoint and caveat');

  const historyPath = `/api/v1/observations?patient_id=${encodeURIComponent(patientId)}&limit=10`;
  const { data: history } = await request(historyPath);
  assert.equal(history.demo_only, true);
  assert.equal(history.count, 1);
  assert.equal(history.items[0].id, prediction.observation_id);
  assert.equal(history.items[0].patient_id, patientId);
  assert.equal(history.items[0].inputs.spo2, 98);
  console.log('✓ Prediction persisted and returned by history');

  const trendPath = '/api/v1/observations/trends?patient_id=' + encodeURIComponent(patientId) + '&limit=50';
  const { data: trends } = await request(trendPath);
  assert.equal(trends.demo_only, true);
  assert.equal(trends.patient_id, patientId);
  assert.equal(trends.observation_count, 1);
  assert.ok(Array.isArray(trends.trends));
  assert.ok(trends.trends.every((item) => item.status === 'insufficient_data'));
  console.log('✓ Descriptive trend endpoint and insufficient-history state');

  const { data: quality } = await request('/api/v1/observations/quality?stale_after_seconds=300&limit=100');
  assert.equal(quality.demo_only, true);
  assert.ok(Array.isArray(quality.items));
  console.log('✓ Observation freshness and completeness endpoint');

  const invalid = await fetch(`${baseUrl}/api/v1/risk/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      patient_id: patientId,
      age: 58,
      heart_rate: 82,
      spo2: 140,
      systolic_bp: 122,
      diastolic_bp: 78,
      temperature: 37,
      respiratory_rate: 16,
    }),
    signal: AbortSignal.timeout(timeoutMs),
  });
  assert.equal(invalid.status, 422, 'Out-of-range vitals should be rejected with 422');
  console.log('✓ Invalid input rejected');

  const alertPatientId = 'SMOKE-ALERT-' + Date.now();
  await request('/api/v1/risk/predict', {
    method: 'POST',
    body: JSON.stringify({
      patient_id: alertPatientId, age: 70, heart_rate: 180, spo2: 78,
      systolic_bp: 80, diastolic_bp: 50, temperature: 39.5, respiratory_rate: 34,
    }),
  });
  const { data: alerts } = await request('/api/v1/alerts?patient_id=' + encodeURIComponent(alertPatientId) + '&limit=10');
  assert.ok(alerts.items.length > 0, 'Elevated synthetic prediction should create a demo alert');
  const alertId = alerts.items[0].id;
  const { data: acknowledged } = await request('/api/v1/alerts/' + alertId + '/acknowledge', {
    method: 'POST', body: JSON.stringify({ actor: 'smoke-test-demo-operator' }),
  });
  assert.equal(acknowledged.item.status, 'acknowledged');
  const { data: resolved } = await request('/api/v1/alerts/' + alertId + '/resolve', {
    method: 'POST', body: JSON.stringify({ actor: 'smoke-test-demo-operator' }),
  });
  assert.equal(resolved.item.status, 'resolved');
  const { data: audit } = await request('/api/v1/alerts/' + alertId + '/audit');
  assert.ok(audit.count >= 3, 'Alert audit should include creation, acknowledgement, and resolution');
  console.log('✓ Persistent alert lifecycle and audit trail');

  const { data: timeline } = await request('/api/v1/patients/' + encodeURIComponent(alertPatientId) + '/timeline?limit=20');
  assert.equal(timeline.demo_only, true);
  const timelineTypes = new Set(timeline.items.map((item) => item.type));
  assert.ok(timelineTypes.has('observation'), 'Timeline should contain the prediction observation');
  assert.ok(timelineTypes.has('alert'), 'Timeline should contain the persistent alert');
  assert.ok(timelineTypes.has('alert_audit'), 'Timeline should contain alert audit events');
  console.log('✓ Unified patient observation, alert, and audit timeline');

  console.log('All live API smoke checks passed. The test creates only fictional synthetic records. Not for clinical use.');
}

main().catch((error) => {
  console.error('VitalGuard API smoke test failed:', error);
  process.exitCode = 1;
});

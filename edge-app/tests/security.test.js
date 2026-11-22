import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import module from 'node:module'
import path from 'node:path'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const srcDir = path.resolve(__dirname, '../src')

module.registerHooks({
  load(url, context, nextLoad) {
    if (url.endsWith('.html') || url.endsWith('.css') || url.endsWith('.client.js')) {
      const filePath = fileURLToPath(url)
      const text = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : ''
      return { format: 'module', source: `export default ${JSON.stringify(text)};`, shortCircuit: true }
    }
    return nextLoad(url, context)
  },
})

function loadClientSandbox() {
  const elements = new Map()
  const makeEl = (id) => ({
    id,
    innerHTML: '',
    innerText: '',
    textContent: '',
    className: '',
    style: { setProperty() {} },
    classList: { add() {}, remove() {}, toggle() {} },
    addEventListener() {},
    replaceChildren() {},
    getAttribute() { return '' },
  })
  const getElementById = (id) => {
    if (!elements.has(id)) elements.set(id, makeEl(id))
    return elements.get(id)
  }

  const sandbox = {
    window: { addEventListener() {} },
    document: {
      getElementById,
      querySelectorAll: () => [],
      createElement: () => makeEl('dyn'),
    },
    console,
    setTimeout,
    clearTimeout,
    setInterval: () => 0,
    Math,
    Number,
    String,
    Date,
    Array,
    Object,
    Set,
    Map,
  }

  const core = fs.readFileSync(path.join(srcDir, 'client/dashboard-core.client.js'), 'utf8')
    .replace('${supabaseUrl}', '""')
    .replace('${supabaseKey}', '""')
    .replace('${topologyHubNode}', '""')
  const insights = fs.readFileSync(path.join(srcDir, 'client/dashboard-insights.client.js'), 'utf8')
  const charts = fs.readFileSync(path.join(srcDir, 'client/dashboard-charts.client.js'), 'utf8')

  vm.createContext(sandbox)
  vm.runInContext(`${core}\n${insights}\n${charts}`, sandbox)
  return { sandbox, elements }
}

test('escapeHtml neutralizes HTML and attribute XSS payloads', () => {
  const { sandbox } = loadClientSandbox()
  const payload = `<img src=x onerror="alert('xss')">&`
  const escaped = sandbox.escapeHtml(payload)
  assert.equal(escaped, '&lt;img src=x onerror=&quot;alert(&#39;xss&#39;)&quot;&gt;&amp;')
  assert.equal(sandbox.safePercent('100%;background:url(x)'), 0)
  assert.equal(sandbox.safePercent(150), 100)
  assert.equal(sandbox.safePercent(-5), 0)
  assert.equal(sandbox.safeMetricNumber('NaN', 7), 7)
})

test('renderTable, renderDiagnostics, and renderAnomalyTags escape untrusted fields', () => {
  const { sandbox, elements } = loadClientSandbox()
  const xss = '<svg/onload=alert(1)>'

  sandbox.renderTable([{
    node_name: xss,
    provider: '<b>prov</b>',
    region: '"region"',
    status: '<script>x</script>',
    cpu_usage_percent: '50%;color:red',
    mem_usage_percent: 42,
    disk_usage_percent: 33,
    scrape_duration_ms: 25,
    recorded_at: xss,
  }])
  const tbodyHtml = elements.get('nodes-table-body').innerHTML
  assert.ok(!tbodyHtml.includes('<svg/onload=alert(1)>'))
  assert.ok(!tbodyHtml.includes('<script>'))
  assert.ok(tbodyHtml.includes('&lt;svg/onload=alert(1)&gt;'))
  assert.ok(tbodyHtml.includes('width: 0%'))

  sandbox.renderDiagnostics({
    status: 'WARNING',
    fleet_health_score: 90,
    anomalies_count: 1,
    diagnostics: [`HeatWave ML 检测: ${xss}`],
  })
  const diagHtml = elements.get('ai-diagnostics-list').innerHTML
  assert.ok(!diagHtml.includes(xss))
  assert.ok(diagHtml.includes('&lt;svg/onload=alert(1)&gt;'))

  sandbox.renderAnomalyTags([{ anomaly_type: xss, open_count: 1, severity: 'HIGH' }])
  const tagsHtml = elements.get('ai-anomaly-tags').innerHTML
  assert.ok(!tagsHtml.includes(xss))
  assert.ok(tagsHtml.includes('&lt;svg/onload=alert(1)&gt;'))
})

test('HTML templates contain no inline event handlers and pin CDN SRI hashes', () => {
  const htmlFiles = [
    path.join(srcDir, 'index.html'),
    ...fs.readdirSync(path.join(srcDir, 'fragments'))
      .filter((name) => name.endsWith('.html'))
      .map((name) => path.join(srcDir, 'fragments', name)),
  ]
  for (const file of htmlFiles) {
    const content = fs.readFileSync(file, 'utf8')
    assert.doesNotMatch(content, /\bon(click|submit|error|load)=/i, `inline handler in ${file}`)
    assert.doesNotMatch(content, /\busa\b/i, `hardcoded private hub in ${file}`)
  }

  const indexHtml = fs.readFileSync(path.join(srcDir, 'index.html'), 'utf8')
  const cdnTags = indexHtml.match(/<(script|link)[^>]+https:\/\/(cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net)[^>]+>/g) || []
  assert.equal(cdnTags.length, 3)
  for (const tag of cdnTags) {
    assert.match(tag, /integrity="sha384-[A-Za-z0-9+/=]+"/)
    assert.match(tag, /crossorigin="anonymous"/)
  }
  assert.doesNotMatch(indexHtml, /@supabase\/supabase-js@2"/)
})

test('Worker enforces security headers, strict CORS, and safe proxy handling', async () => {
  const { default: worker } = await import('../src/index.ts')
  const env = {
    API_BACKEND_URL: 'https://backend.example.internal',
    INTERNAL_API_SECRET: 'test-secret',
    SUPABASE_URL: 'https://demo.supabase.co',
    SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_demo',
    CF_ACCESS_CLIENT_ID: 'cid',
    CF_ACCESS_CLIENT_SECRET: 'csec',
  }

  const rootRes = await worker.fetch(new Request('https://modo.example/'), env, {})
  assert.equal(rootRes.status, 200)
  assert.equal(rootRes.headers.get('strict-transport-security'), 'max-age=31536000')
  assert.equal(rootRes.headers.get('x-content-type-options'), 'nosniff')
  assert.equal(rootRes.headers.get('x-frame-options'), 'DENY')
  assert.equal(rootRes.headers.get('referrer-policy'), 'strict-origin-when-cross-origin')
  assert.equal(rootRes.headers.get('permissions-policy'), 'camera=(), microphone=(), geolocation=()')
  assert.equal(rootRes.headers.get('access-control-allow-origin'), null)
  const csp = rootRes.headers.get('content-security-policy') || ''
  assert.ok(csp.includes('https://demo.supabase.co'))
  assert.ok(csp.includes('wss://demo.supabase.co'))
  const nonceMatch = csp.match(/nonce-([A-Za-z0-9+/=]+)/)
  assert.ok(nonceMatch)
  const html = await rootRes.text()
  assert.ok(html.includes(`<script nonce="${nonceMatch[1]}">`))

  const origFetch = globalThis.fetch
  try {
    let cancelled = false
    let seenInit = null
    globalThis.fetch = async (_url, init) => {
      seenInit = init
      const stream = new ReadableStream({ cancel() { cancelled = true } })
      return new Response(stream, {
        status: 302,
        headers: {
          Location: 'https://team.cloudflareaccess.com/cdn-cgi/access/login',
          'Set-Cookie': 'CF_AppSession=secret',
        },
      })
    }
    const redirRes = await worker.fetch(new Request('https://modo.example/api/health'), env, {})
    assert.equal(seenInit.redirect, 'manual')
    assert.equal(redirRes.status, 502)
    assert.equal(cancelled, true)
    assert.equal(redirRes.headers.get('location'), null)
    assert.equal(redirRes.headers.get('set-cookie'), null)
    assert.equal(redirRes.headers.get('x-frame-options'), 'DENY')

    globalThis.fetch = async () => new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json', 'Set-Cookie': 'leak=1' },
    })
    const crossRes = await worker.fetch(new Request('https://modo.example/api/health', {
      headers: { Origin: 'https://evil.example' },
    }), env, {})
    assert.equal(crossRes.headers.get('access-control-allow-origin'), null)
    assert.equal(crossRes.headers.get('set-cookie'), null)

    const sameRes = await worker.fetch(new Request('https://modo.example/api/health', {
      headers: { Origin: 'https://modo.example' },
    }), env, {})
    assert.equal(sameRes.headers.get('access-control-allow-origin'), 'https://modo.example')

    const optRes = await worker.fetch(new Request('https://modo.example/api/health', {
      method: 'OPTIONS',
      headers: { Origin: 'https://modo.example', 'Access-Control-Request-Method': 'GET' },
    }), env, {})
    assert.ok(!(optRes.headers.get('access-control-allow-methods') || '').includes('POST'))
  } finally {
    globalThis.fetch = origFetch
  }
})

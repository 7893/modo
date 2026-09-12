import { Hono } from 'hono'
import { cors } from 'hono/cors'

type Bindings = {
  API_BACKEND_URL: string
  SUPABASE_URL?: string
  SUPABASE_ANON_KEY?: string
  INTERNAL_API_SECRET?: string
}

const NO_CACHE_HEADERS = {
  'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
  'Pragma': 'no-cache'
} as const

const app = new Hono<{ Bindings: Bindings }>()

// Global CORS Middleware
app.use('*', cors({
  origin: '*',
  allowMethods: ['GET', 'POST', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'Authorization']
}))

/**
 * Proxy a request to the private backend gateway.
 *
 * Security notes:
 * - The backend address is read only from env; it is never inlined or echoed.
 * - On failure we log full details to the Worker console (private) and return
 *   a generic message to the client, so the internal address and low-level
 *   error text are never exposed in the HTTP response.
 */
async function proxy(c: any, path: string, cache: boolean = true) {
  const backend = c.env.API_BACKEND_URL
  if (!backend) {
    console.error('[proxy] API_BACKEND_URL is not configured')
    return c.json({ status: 'error', message: 'Service temporarily unavailable' }, 503)
  }

  try {
    const res = await fetch(`${backend}${path}`, {
      headers: {
        'User-Agent': 'MODO-Edge-Worker/1.0',
        'X-Internal-Secret': c.env.INTERNAL_API_SECRET || ''
      }
    })
    const data = await res.json()
    return c.json(data, res.status as any, cache ? NO_CACHE_HEADERS : undefined)
  } catch (err: any) {
    // Log details privately; never return them to the client.
    console.error(`[proxy] Upstream request failed for ${path}: ${err?.message}`)
    return c.json({ status: 'error', message: 'Service temporarily unavailable' }, 502)
  }
}

// Proxy API: Nodes Latest Telemetry
app.get('/api/nodes/latest', (c) => proxy(c, '/api/metrics/latest'))

// Proxy API: Node metadata summary
app.get('/api/nodes/summary', (c) => proxy(c, '/api/nodes/summary'))

// Proxy API: Health check
app.get('/api/health', (c) => proxy(c, '/health', false))

// Proxy API: AI Diagnostics
app.get('/api/ai/diagnostics', (c) => proxy(c, '/api/ai/diagnostics'))

// Proxy API: Metrics History
app.get('/api/metrics/history', (c) => {
  const url = new URL(c.req.url)
  const node = encodeURIComponent(url.searchParams.get('node') || '')
  const hours = encodeURIComponent(url.searchParams.get('hours') || '24')
  return proxy(c, `/api/metrics/history?node=${node}&hours=${hours}`)
})

// Proxy API: HeatWave Hourly Analytics
app.get('/api/analytics/hourly', (c) => {
  const url = new URL(c.req.url)
  const node = encodeURIComponent(url.searchParams.get('node') || '')
  const hours = encodeURIComponent(url.searchParams.get('hours') || '48')
  return proxy(c, `/api/analytics/hourly?node=${node}&hours=${hours}`)
})

// Proxy API: HeatWave Fleet Health Report
app.get('/api/analytics/fleet', (c) => proxy(c, '/api/analytics/fleet'))

// Proxy API: HeatWave Anomaly Dashboard
app.get('/api/analytics/anomalies', (c) => proxy(c, '/api/analytics/anomalies'))

// Proxy API: HeatWave Cluster Status
app.get('/api/analytics/heatwave-status', (c) => proxy(c, '/api/analytics/heatwave-status'))

// Proxy API: Latency Forecast (HeatWave AutoML + EMA)
app.get('/api/analytics/latency-forecast', (c) => proxy(c, '/api/analytics/latency-forecast'))

// Proxy API: HeatWave ML Features
app.get('/api/analytics/ml-features', (c) => proxy(c, '/api/analytics/ml-features'))

import htmlTemplate from './index.html'

// Frontend Dashboard SPA
app.get('/', (c) => {
  const supabaseUrl = c.env.SUPABASE_URL || ''
  const supabaseKey = c.env.SUPABASE_ANON_KEY || ''

  const finalHtml = htmlTemplate
    .replace('${supabaseUrl}', supabaseUrl)
    .replace('${supabaseKey}', supabaseKey)

  return c.html(finalHtml, 200, NO_CACHE_HEADERS)
})


export default {
  fetch: app.fetch,
  async scheduled(event: any, env: Bindings, ctx: any) {
    const backend = env.API_BACKEND_URL
    if (!backend) {
      console.error('[Cron] API_BACKEND_URL is not configured')
      return
    }
    try {
      const res = await fetch(`${backend}/api/maintenance/prune`, {
        method: 'POST',
        headers: { 'X-Internal-Secret': env.INTERNAL_API_SECRET || '' }
      });
      console.log(`[Cron] Triggered at ${event.cron}. Status: ${res.status}`);
      const data = await res.text();
      console.log(`[Cron] Output: ${data}`);
    } catch (e) {
      console.error(`[Cron] Error: ${e}`);
    }
  }
}

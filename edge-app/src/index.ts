import { Hono, type Context } from 'hono'
import { cors } from 'hono/cors'

import htmlTemplate from './index.html'
import tailwindCss from './tailwind.generated.css'
import aiPanel from './fragments/ai.html'
import authModal from './fragments/auth-modal.html'
import inventoryPanel from './fragments/inventory.html'
import latencyPanel from './fragments/latency.html'
import mapPanel from './fragments/map.html'
import overviewPanel from './fragments/overview.html'
import resourcePanel from './fragments/resource.html'
import dashboardAuthScript from './client/dashboard-auth.client.js'
import dashboardChartsScript from './client/dashboard-charts.client.js'
import dashboardCoreScript from './client/dashboard-core.client.js'
import dashboardInsightsScript from './client/dashboard-insights.client.js'

type AppEnv = {
  Bindings: CloudflareBindings & { TOPOLOGY_HUB_NODE?: string }
}

const NO_CACHE_HEADERS = {
  'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
  'Pragma': 'no-cache'
} as const

const app = new Hono<AppEnv>()

function inlineScriptString(value: string | undefined): string {
  return JSON.stringify(value || '')
    .replace(/</g, '\\u003c')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029')
}

app.use('*', cors({
  origin: '*',
  allowMethods: ['GET', 'POST', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'Authorization']
}))

/** Proxy an authenticated request to the private backend gateway. */
async function proxy(c: Context<AppEnv>, path: string, noStore: boolean = true): Promise<Response> {
  const backend = c.env.API_BACKEND_URL
  const internalSecret = c.env.INTERNAL_API_SECRET
  if (!backend || !internalSecret) {
    console.error(JSON.stringify({ message: 'proxy configuration missing', path }))
    return c.json({ status: 'error', message: 'Service temporarily unavailable' }, 503)
  }

  try {
    const clientIp = c.req.header('CF-Connecting-IP')
      || c.req.header('X-Forwarded-For')?.split(',')[0]?.trim()
      || 'unknown'
    const response = await fetch(`${backend}${path}`, {
      headers: {
        'User-Agent': 'MODO-Edge-Worker/1.0',
        'X-Internal-Secret': internalSecret,
        'X-MODO-Client-IP': clientIp
      }
    })

    if (response.status >= 500) {
      console.error(JSON.stringify({ message: 'backend request failed', path, status: response.status }))
      return c.json({ status: 'error', message: 'Service temporarily unavailable' }, 502)
    }

    const headers = new Headers(response.headers)
    if (noStore) {
      for (const [name, value] of Object.entries(NO_CACHE_HEADERS)) {
        headers.set(name, value)
      }
    }
    return new Response(response.body, { status: response.status, headers })
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error)
    console.error(JSON.stringify({ message: 'upstream request failed', path, error: message }))
    return c.json({ status: 'error', message: 'Service temporarily unavailable' }, 502)
  }
}

app.get('/api/dashboard/overview', (c) => proxy(c, '/api/dashboard/overview'))
app.get('/api/nodes/latest', (c) => proxy(c, '/api/metrics/latest'))
app.get('/api/nodes/summary', (c) => proxy(c, '/api/nodes/summary'))
app.get('/api/health', (c) => proxy(c, '/health', false))
app.get('/api/ai/diagnostics', (c) => proxy(c, '/api/ai/diagnostics'))

app.get('/api/metrics/history', (c) => {
  const url = new URL(c.req.url)
  const node = encodeURIComponent(url.searchParams.get('node') || '')
  const hours = encodeURIComponent(url.searchParams.get('hours') || '24')
  return proxy(c, `/api/metrics/history?node=${node}&hours=${hours}`)
})

app.get('/api/analytics/hourly', (c) => {
  const url = new URL(c.req.url)
  const node = encodeURIComponent(url.searchParams.get('node') || '')
  const hours = encodeURIComponent(url.searchParams.get('hours') || '48')
  return proxy(c, `/api/analytics/hourly?node=${node}&hours=${hours}`)
})

app.get('/api/analytics/fleet', (c) => proxy(c, '/api/analytics/fleet'))
app.get('/api/analytics/anomalies', (c) => proxy(c, '/api/analytics/anomalies'))
app.get('/api/analytics/heatwave-status', (c) => proxy(c, '/api/analytics/heatwave-status'))
app.get('/api/analytics/latency-forecast', (c) => proxy(c, '/api/analytics/latency-forecast'))
app.get('/api/analytics/ml-features', (c) => proxy(c, '/api/analytics/ml-features'))

app.get('/', (c) => {
  const finalHtml = htmlTemplate
    .replace('${overviewPanel}', () => overviewPanel)
    .replace('${mapPanel}', () => mapPanel)
    .replace('${resourcePanel}', () => resourcePanel)
    .replace('${latencyPanel}', () => latencyPanel)
    .replace('${inventoryPanel}', () => inventoryPanel)
    .replace('${aiPanel}', () => aiPanel)
    .replace('${authModal}', () => authModal)
    .replace('${dashboardCoreScript}', () => dashboardCoreScript)
    .replace('${dashboardInsightsScript}', () => dashboardInsightsScript)
    .replace('${dashboardChartsScript}', () => dashboardChartsScript)
    .replace('${dashboardAuthScript}', () => dashboardAuthScript)
    .replace('${tailwindCss}', () => tailwindCss)
    .replace('${supabaseUrl}', () => inlineScriptString(c.env.SUPABASE_URL))
    .replace('${supabaseKey}', () => inlineScriptString(c.env.SUPABASE_PUBLISHABLE_KEY))
    .replace('${topologyHubNode}', () => inlineScriptString(c.env.TOPOLOGY_HUB_NODE))

  return c.html(finalHtml, 200, NO_CACHE_HEADERS)
})

export default {
  fetch: app.fetch,
  async scheduled(event: ScheduledController, env: CloudflareBindings, _ctx: ExecutionContext): Promise<void> {
    const backend = env.API_BACKEND_URL
    const internalSecret = env.INTERNAL_API_SECRET
    if (!backend || !internalSecret) {
      console.error(JSON.stringify({ message: 'cron configuration missing', cron: event.cron }))
      return
    }

    try {
      const response = await fetch(`${backend}/api/maintenance/prune`, {
        method: 'POST',
        headers: { 'X-Internal-Secret': internalSecret }
      })
      console.log(JSON.stringify({ message: 'maintenance cron completed', cron: event.cron, status: response.status }))
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error)
      console.error(JSON.stringify({ message: 'maintenance cron failed', cron: event.cron, error: message }))
    }
  }
} satisfies ExportedHandler<CloudflareBindings>

import { Hono } from 'hono'
import { cors } from 'hono/cors'

type Bindings = {
  API_BACKEND_URL: string
  SUPABASE_URL?: string
  SUPABASE_ANON_KEY?: string
  INTERNAL_API_SECRET?: string
}

const app = new Hono<{ Bindings: Bindings }>()

// Global CORS Middleware
app.use('*', cors({
  origin: '*',
  allowMethods: ['GET', 'POST', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'Authorization']
}))

// Proxy API: Nodes Latest Telemetry
app.get('/api/nodes/latest', async (c) => {
  const backend = c.env.API_BACKEND_URL || 'https://api-nexus.8n8m.cfd'
  try {
    const res = await fetch(`${backend}/api/metrics/latest`, {
      headers: { 'User-Agent': 'Nexus-Edge-Worker/1.0', 'X-Internal-Secret': c.env.INTERNAL_API_SECRET || '' }
    })
    const data = await res.json()
    return c.json(data, res.status as any)
  } catch (err: any) {
    return c.json({ status: 'error', secret: c.env.INTERNAL_API_SECRET, message: 'Backend gateway unreachable', error: err.message }, 502)
  }
})

// Proxy API: AI Diagnostics
app.get('/api/ai/diagnostics', async (c) => {
  const backend = c.env.API_BACKEND_URL || 'https://api-nexus.8n8m.cfd'
  try {
    const res = await fetch(`${backend}/api/ai/diagnostics`, {
      headers: { 'User-Agent': 'Nexus-Edge-Worker/1.0', 'X-Internal-Secret': c.env.INTERNAL_API_SECRET || '' }
    })
    const data = await res.json()
    return c.json(data, res.status as any)
  } catch (err: any) {
    return c.json({ status: 'error', secret: c.env.INTERNAL_API_SECRET, message: 'Diagnostics unreachable', error: err.message }, 502)
  }
})

// Proxy API: Metrics History
app.get('/api/metrics/history', async (c) => {
  const backend = c.env.API_BACKEND_URL || 'https://api-nexus.8n8m.cfd'
  const url = new URL(c.req.url)
  const node = url.searchParams.get('node') || ''
  const hours = url.searchParams.get('hours') || '24'
  try {
    const res = await fetch(`${backend}/api/metrics/history?node=${node}&hours=${hours}`, {
      headers: { 'User-Agent': 'Nexus-Edge-Worker/1.0', 'X-Internal-Secret': c.env.INTERNAL_API_SECRET || '' }
    })
    const data = await res.json()
    return c.json(data, res.status as any)
  } catch (err: any) {
    return c.json({ status: 'error', secret: c.env.INTERNAL_API_SECRET, message: 'History query failed', error: err.message }, 502)
  }
})

import htmlTemplate from './index.html'

// Frontend Dashboard SPA
app.get('/', (c) => {
  const supabaseUrl = c.env.SUPABASE_URL || 'https://qkpwuxaylvzycapkojvq.supabase.co'
  const supabaseKey = c.env.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFrcHd1eGF5bHZ6eWNhcGtvanZxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM0MTI1NTksImV4cCI6MjA4ODk4ODU1OX0.iasxckoGYjRiLtaZcrmpwNW8QDuqh-BMGNy3rbmK4mQ'

  const finalHtml = htmlTemplate
    .replace('${supabaseUrl}', supabaseUrl)
    .replace('${supabaseKey}', supabaseKey)

  return c.html(finalHtml, 200, {
    'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
    'Pragma': 'no-cache'
  })
})

export default app

import { Hono } from 'hono'
import { cors } from 'hono/cors'

type Bindings = {
  API_BACKEND_URL: string
  INTERNAL_API_SECRET?: string
}

const app = new Hono<{ Bindings: Bindings }>()

app.use('*', cors({
  origin: '*',
  allowMethods: ['GET', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'Authorization']
}))

// Node metadata
app.get('/api/nodes/summary', async (c) => {
  const backend = c.env.API_BACKEND_URL || 'https://api-modo.8n8m.cfd'
  try {
    const res = await fetch(`${backend}/api/nodes/summary`, {
      headers: { 'X-Internal-Secret': c.env.INTERNAL_API_SECRET || '' }
    })
    return c.json(await res.json(), res.status as any)
  } catch (err: any) {
    return c.json({ status: 'error', message: 'Backend unreachable', error: err.message }, 502)
  }
})

// Health check passthrough
app.get('/api/health', async (c) => {
  const backend = c.env.API_BACKEND_URL || 'https://api-modo.8n8m.cfd'
  try {
    const res = await fetch(`${backend}/health`, {
      headers: { 'X-Internal-Secret': c.env.INTERNAL_API_SECRET || '' }
    })
    return c.json(await res.json(), res.status as any)
  } catch (err: any) {
    return c.json({ status: 'error', message: 'Backend unreachable', error: err.message }, 502)
  }
})

import htmlTemplate from './index.html'

app.get('/', (c) => {
  return c.html(htmlTemplate, 200, {
    'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
    'Pragma': 'no-cache'
  })
})

export default { fetch: app.fetch }

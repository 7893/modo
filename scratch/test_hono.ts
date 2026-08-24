import { Hono } from 'hono'
const app = new Hono()
app.get('/', (c) => {
  return c.html('hello', 200, { 'X-Test': '123' })
})

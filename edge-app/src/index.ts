import { Hono } from 'hono'
import { cors } from 'hono/cors'

type Bindings = {
  API_BACKEND_URL: string
  SUPABASE_URL?: string
  SUPABASE_ANON_KEY?: string
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
      headers: { 'User-Agent': 'Nexus-Edge-Worker/1.0' }
    })
    const data = await res.json()
    return c.json(data, res.status as any)
  } catch (err: any) {
    return c.json({ status: 'error', message: 'Backend gateway unreachable', error: err.message }, 502)
  }
})

// Proxy API: AI Diagnostics
app.get('/api/ai/diagnostics', async (c) => {
  const backend = c.env.API_BACKEND_URL || 'https://api-nexus.8n8m.cfd'
  try {
    const res = await fetch(`${backend}/api/ai/diagnostics`, {
      headers: { 'User-Agent': 'Nexus-Edge-Worker/1.0' }
    })
    const data = await res.json()
    return c.json(data, res.status as any)
  } catch (err: any) {
    return c.json({ status: 'error', message: 'Diagnostics unreachable', error: err.message }, 502)
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
      headers: { 'User-Agent': 'Nexus-Edge-Worker/1.0' }
    })
    const data = await res.json()
    return c.json(data, res.status as any)
  } catch (err: any) {
    return c.json({ status: 'error', message: 'History query failed', error: err.message }, 502)
  }
})

// Frontend Dashboard SPA
app.get('/', (c) => {
  const supabaseUrl = c.env.SUPABASE_URL || 'https://qkpwuxaylvzycapkojvq.supabase.co'
  const supabaseKey = c.env.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFrcHd1eGF5bHZ6eWNhcGtvanZxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM0MTI1NTksImV4cCI6MjA4ODk4ODU1OX0.iasxckoGYjRiLtaZcrmpwNW8QDuqh-BMGNy3rbmK4mQ'

  const html = `<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NEXUS // 全球多云算力遥测与 AI 智能中枢</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🌐</text></svg>">
  
  <!-- Tailwind CSS & FontAwesome -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: {
              50: '#ecfeff',
              400: '#22d3ee',
              500: '#06b6d4',
              600: '#0891b2',
              glow: '#00f2fe'
            },
            dark: {
              bg: '#070a13',
              card: '#0f172a',
              border: '#1e293b'
            }
          },
          fontFamily: {
            mono: ['JetBrains Mono', 'Fira Code', 'monospace']
          }
        }
      }
    }
  </script>
  
  <!-- ECharts 5, Supabase JS & FontAwesome -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.0/echarts.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  
  <style>
    body {
      background-color: #070a13;
      background-image: 
        radial-gradient(at 0% 0%, rgba(6, 182, 212, 0.08) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.08) 0px, transparent 50%);
      color: #e2e8f0;
    }
    .glass-card {
      background: rgba(15, 23, 42, 0.75);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(30, 41, 59, 0.8);
      box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    .glow-cyan {
      box-shadow: 0 0 20px rgba(6, 182, 212, 0.3);
    }
    .pulse-beacon {
      animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: .5; transform: scale(1.1); }
    }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #070a13; }
    ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #0891b2; }
  </style>
</head>
<body class="min-h-screen font-sans antialiased flex flex-col selection:bg-cyan-500 selection:text-black">

  <!-- TOP NAVIGATION BAR -->
  <header class="sticky top-0 z-50 glass-card border-b border-dark-border px-6 py-3.5 flex items-center justify-between">
    <div class="flex items-center space-x-4">
      <div class="flex items-center space-x-2">
        <div class="w-3 h-3 rounded-full bg-cyan-400 animate-ping"></div>
        <div class="w-3 h-3 rounded-full bg-cyan-500 -ml-5"></div>
        <span class="text-xl font-bold tracking-widest bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-teal-300 to-indigo-400 font-mono">
          NEXUS // 2026
        </span>
      </div>
      <span class="hidden md:inline-block text-xs uppercase px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/50 font-mono">
        Cloudflare Edge Gateway
      </span>
    </div>

    <!-- Center Live Status -->
    <div class="hidden lg:flex items-center space-x-6 text-xs font-mono">
      <div class="flex items-center space-x-2">
        <span class="text-slate-400">集群状态:</span>
        <span id="fleet-health-badge" class="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/60 font-semibold">
          100% HEALTHY
        </span>
      </div>
      <div class="flex items-center space-x-2">
        <span class="text-slate-400">活跃节点:</span>
        <span id="active-nodes-count" class="text-cyan-400 font-bold">10 / 10 ONLINE</span>
      </div>
      <div class="flex items-center space-x-2">
        <span class="text-slate-400">同步时钟:</span>
        <span id="sync-timer" class="text-slate-300">Auto: 15s</span>
      </div>
    </div>

    <!-- Right Actions / User Profile -->
    <div class="flex items-center space-x-3">
      <button id="refresh-btn" onclick="fetchData()" class="px-3 py-1.5 rounded-lg text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition flex items-center space-x-1.5">
        <i class="fa-solid fa-arrows-rotate" id="refresh-icon"></i>
        <span>立即刷新</span>
      </button>
      
      <div id="auth-section" class="flex items-center">
        <button id="login-btn" onclick="toggleAuthModal()" class="px-3.5 py-1.5 rounded-lg text-xs font-mono bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-black font-semibold shadow transition">
          <i class="fa-solid fa-shield-halved mr-1"></i>
          <span>Supabase 登录</span>
        </button>
        <div id="user-profile" class="hidden items-center space-x-2">
          <span id="user-email" class="text-xs text-slate-300 font-mono"></span>
          <button onclick="handleLogout()" class="px-2 py-1 text-xs text-rose-400 hover:text-rose-300 font-mono">
            <i class="fa-solid fa-right-from-bracket"></i>
          </button>
        </div>
      </div>
    </div>
  </header>

  <!-- MAIN CONTAINER -->
  <main class="flex-1 p-4 md:p-6 space-y-6 max-w-[1600px] w-full mx-auto">

    <!-- KPI STATS ROW -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <!-- Card 1 -->
      <div class="glass-card rounded-xl p-4 flex items-center justify-between relative overflow-hidden">
        <div class="space-y-1 z-10">
          <div class="text-xs text-slate-400 font-mono uppercase tracking-wider">生产在线节点</div>
          <div class="text-2xl font-bold font-mono text-cyan-400" id="stat-online-nodes">10 <span class="text-xs font-normal text-slate-400">/ 10</span></div>
          <div class="text-xs text-emerald-400 flex items-center space-x-1">
            <i class="fa-solid fa-circle-check text-[10px]"></i>
            <span>东京 (5) · 美东 (3) · 新加坡 · 北京</span>
          </div>
        </div>
        <div class="w-12 h-12 rounded-xl bg-cyan-950/60 border border-cyan-800/40 flex items-center justify-center text-cyan-400 text-xl">
          <i class="fa-solid fa-server"></i>
        </div>
      </div>

      <!-- Card 2 -->
      <div class="glass-card rounded-xl p-4 flex items-center justify-between relative overflow-hidden">
        <div class="space-y-1 z-10">
          <div class="text-xs text-slate-400 font-mono uppercase tracking-wider">全球平均探测延迟</div>
          <div class="text-2xl font-bold font-mono text-indigo-400" id="stat-avg-latency">-- <span class="text-xs font-normal text-slate-400">ms</span></div>
          <div class="text-xs text-slate-400">同区域 14ms · 跨洋 ~350ms</div>
        </div>
        <div class="w-12 h-12 rounded-xl bg-indigo-950/60 border border-indigo-800/40 flex items-center justify-center text-indigo-400 text-xl">
          <i class="fa-solid fa-bolt"></i>
        </div>
      </div>

      <!-- Card 3 -->
      <div class="glass-card rounded-xl p-4 flex items-center justify-between relative overflow-hidden">
        <div class="space-y-1 z-10">
          <div class="text-xs text-slate-400 font-mono uppercase tracking-wider">全网平均内存占用</div>
          <div class="text-2xl font-bold font-mono text-teal-400" id="stat-avg-mem">-- <span class="text-xs font-normal text-slate-400">%</span></div>
          <div class="text-xs text-slate-400">健康负载状态良好</div>
        </div>
        <div class="w-12 h-12 rounded-xl bg-teal-950/60 border border-teal-800/40 flex items-center justify-center text-teal-400 text-xl">
          <i class="fa-solid fa-microchip"></i>
        </div>
      </div>

      <!-- Card 4 -->
      <div class="glass-card rounded-xl p-4 flex items-center justify-between relative overflow-hidden">
        <div class="space-y-1 z-10">
          <div class="text-xs text-slate-400 font-mono uppercase tracking-wider">时序入库引擎</div>
          <div class="text-2xl font-bold font-mono text-amber-400">HeatWave</div>
          <div class="text-xs text-emerald-400 flex items-center space-x-1">
            <i class="fa-solid fa-database text-[10px]"></i>
            <span>MySQL 26.7 Cloud Ingesting</span>
          </div>
        </div>
        <div class="w-12 h-12 rounded-xl bg-amber-950/60 border border-amber-800/40 flex items-center justify-center text-amber-400 text-xl">
          <i class="fa-solid fa-database"></i>
        </div>
      </div>
    </div>

    <!-- MIDDLE ROW: MAP + AI INSIGHTS -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Left 2 Cols: Global Topology Radar Map -->
      <div class="lg:col-span-2 glass-card rounded-xl p-5 flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center space-x-2">
            <i class="fa-solid fa-satellite-dish text-cyan-400"></i>
            <h2 class="text-sm font-bold font-mono uppercase tracking-wider text-slate-200">全球多云拓扑与节点雷达</h2>
          </div>
          <div class="flex items-center space-x-3 text-xs font-mono text-slate-400">
            <span class="flex items-center space-x-1"><span class="w-2 h-2 rounded-full bg-cyan-400"></span><span>在线探针</span></span>
            <span class="flex items-center space-x-1"><span class="w-2 h-2 rounded-full bg-purple-400"></span><span>数据中枢</span></span>
          </div>
        </div>
        
        <!-- Radar Map Container -->
        <div id="world-map-chart" class="w-full h-[380px] rounded-lg"></div>
      </div>

      <!-- Right 1 Col: AI Diagnostics Summary -->
      <div class="glass-card rounded-xl p-5 flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center space-x-2">
              <i class="fa-solid fa-brain text-purple-400"></i>
              <h2 class="text-sm font-bold font-mono uppercase tracking-wider text-slate-200">AI 智能运维中枢</h2>
            </div>
            <span id="ai-score-pill" class="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-purple-950 text-purple-300 border border-purple-800/60">
              HEALTH: 100%
            </span>
          </div>

          <div class="space-y-3" id="ai-diagnostics-list">
            <div class="p-3.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs space-y-1.5">
              <div class="flex items-center justify-between text-cyan-400 font-mono font-semibold">
                <span><i class="fa-solid fa-shield-heart mr-1.5"></i>智能全网健康度</span>
                <span class="text-[10px] text-slate-500">Autonomous Agent</span>
              </div>
              <p class="text-slate-300 leading-relaxed text-[11px]" id="diag-summary-text">
                全网 10 台生产虚拟机运行平稳，东京、美东、新加坡与北京网络时延与负载正常。
              </p>
            </div>

            <div class="p-3.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs space-y-2 font-mono">
              <div class="text-slate-400 text-[11px] uppercase">中枢运行指标</div>
              <div class="grid grid-cols-2 gap-2 text-[11px]">
                <div class="p-2 rounded bg-slate-950/60 border border-slate-800/50">
                  <div class="text-slate-500 text-[10px]">时序入库周期</div>
                  <div class="text-cyan-400 font-bold">60s / 批次</div>
                </div>
                <div class="p-2 rounded bg-slate-950/60 border border-slate-800/50">
                  <div class="text-slate-500 text-[10px]">隧道协议</div>
                  <div class="text-indigo-400 font-bold">Cloudflare QUIC</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="pt-4 border-t border-dark-border flex items-center justify-between text-[11px] font-mono text-slate-400">
          <span>AI 诊断引擎: v2.6.7</span>
          <span class="text-emerald-400 flex items-center"><i class="fa-solid fa-circle-check mr-1"></i>实时在线</span>
        </div>
      </div>

    </div>

    <!-- METRICS CHARTS ROW -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Chart 1: Memory & Disk Usage per node -->
      <div class="glass-card rounded-xl p-5">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center space-x-2">
            <i class="fa-solid fa-chart-column text-cyan-400"></i>
            <h2 class="text-sm font-bold font-mono uppercase tracking-wider text-slate-200">各节点内存与磁盘占用率 (%)</h2>
          </div>
        </div>
        <div id="resource-bar-chart" class="w-full h-[280px]"></div>
      </div>

      <!-- Chart 2: Latency Spectrum per node -->
      <div class="glass-card rounded-xl p-5">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center space-x-2">
            <i class="fa-solid fa-gauge-high text-indigo-400"></i>
            <h2 class="text-sm font-bold font-mono uppercase tracking-wider text-slate-200">全网延迟阶梯分析 (ms)</h2>
          </div>
        </div>
        <div id="latency-chart" class="w-full h-[280px]"></div>
      </div>
    </div>

    <!-- DETAILED NODE INVENTORY TABLE -->
    <div class="glass-card rounded-xl p-5">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center space-x-2">
          <i class="fa-solid fa-list-check text-cyan-400"></i>
          <h2 class="text-sm font-bold font-mono uppercase tracking-wider text-slate-200">全球节点实时遥测全景明细</h2>
        </div>
        <span class="text-xs text-slate-400 font-mono">共纳管 10 台生产虚拟机</span>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs font-mono">
          <thead class="bg-slate-900/80 text-slate-400 uppercase text-[11px] border-b border-dark-border">
            <tr>
              <th class="py-3 px-4">节点</th>
              <th class="py-3 px-4">云服务商 / 地区</th>
              <th class="py-3 px-4">主机 IP</th>
              <th class="py-3 px-4">状态</th>
              <th class="py-3 px-4">CPU使用率</th>
              <th class="py-3 px-4">内存占用</th>
              <th class="py-3 px-4">磁盘占用</th>
              <th class="py-3 px-4">探测延迟</th>
              <th class="py-3 px-4">最后采集时间</th>
            </tr>
          </thead>
          <tbody id="nodes-table-body" class="divide-y divide-dark-border text-slate-300">
            <tr>
              <td colspan="8" class="text-center py-8 text-slate-500">
                <i class="fa-solid fa-spinner fa-spin mr-2"></i>正在连接 Cloudflare Tunnel 加载数据...
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

  </main>

  <!-- SUPABASE AUTH MODAL -->
  <div id="auth-modal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
    <div class="glass-card rounded-2xl p-6 max-w-md w-full border border-cyan-500/30 relative">
      <button onclick="toggleAuthModal()" class="absolute top-4 right-4 text-slate-400 hover:text-slate-200">
        <i class="fa-solid fa-xmark text-lg"></i>
      </button>

      <div class="text-center mb-6 space-y-1">
        <div class="inline-block p-3 rounded-full bg-cyan-950/60 border border-cyan-800/40 text-cyan-400 mb-2">
          <i class="fa-solid fa-fingerprint text-2xl"></i>
        </div>
        <h3 class="text-lg font-bold font-mono text-white">NEXUS COMMAND ACCESS</h3>
        <p class="text-xs text-slate-400">使用 Supabase 账号安全验证身份</p>
      </div>

      <form id="auth-form" onsubmit="handleAuth(event)" class="space-y-4 font-mono text-xs">
        <div>
          <label class="block text-slate-300 mb-1">邮箱地址</label>
          <input type="email" id="auth-email" required class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-cyan-400" placeholder="admin@example.com">
        </div>
        <div>
          <label class="block text-slate-300 mb-1">登录密码</label>
          <input type="password" id="auth-password" required class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white focus:outline-none focus:border-cyan-400" placeholder="••••••••">
        </div>

        <div id="auth-error" class="hidden p-2.5 rounded bg-rose-950/80 border border-rose-800/60 text-rose-300 text-[11px]"></div>

        <button type="submit" id="auth-submit-btn" class="w-full py-2.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-black font-bold tracking-wider transition">
          立即登录
        </button>
      </form>
    </div>
  </div>

  <!-- FOOTER -->
  <footer class="glass-card border-t border-dark-border py-4 px-6 text-center text-xs font-mono text-slate-500">
    <span>Project Nexus © 2026 // Powered by Cloudflare Workers, Hono, MySQL HeatWave & Supabase Auth</span>
  </footer>

  <!-- SCRIPT LOGIC -->
  <script>
    const SUPABASE_URL = "${supabaseUrl}";
    const SUPABASE_KEY = "${supabaseKey}";
    let supabaseClient = null;

    try {
      if (typeof window.supabase !== 'undefined' && window.supabase.createClient && SUPABASE_URL && SUPABASE_KEY) {
        supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);
      }
    } catch (e) {
      console.warn('Supabase init skipped:', e);
    }

    let resourceChart = null;
    let latencyChart = null;
    let mapChart = null;
    let countdown = 15;

    // Initialize Charts safely
    function initCharts() {
      if (typeof echarts === 'undefined') return;
      try {
        const resEl = document.getElementById('resource-bar-chart');
        if (resEl) resourceChart = echarts.init(resEl);

        const latEl = document.getElementById('latency-chart');
        if (latEl) latencyChart = echarts.init(latEl);

        const mapEl = document.getElementById('world-map-chart');
        if (mapEl) mapChart = echarts.init(mapEl);

        window.addEventListener('resize', () => {
          resourceChart?.resize();
          latencyChart?.resize();
          mapChart?.resize();
        });
      } catch (e) {
        console.warn('Chart init error:', e);
      }
    }

    // Fetch live data from backend proxy
    async function fetchData() {
      const icon = document.getElementById('refresh-icon');
      icon?.classList.add('fa-spin');

      try {
        const latestRes = await fetch('/api/nodes/latest');
        const latestJson = await latestRes.json();
        
        if (latestJson.status === 'success' && Array.isArray(latestJson.data)) {
          try { renderTable(latestJson.data); } catch(e) { console.error('renderTable error:', e); }
          try { renderKPIs(latestJson.data); } catch(e) { console.error('renderKPIs error:', e); }
          try { renderResourceChart(latestJson.data); } catch(e) { console.error('renderResourceChart error:', e); }
          try { renderLatencyChart(latestJson.data); } catch(e) { console.error('renderLatencyChart error:', e); }
          try { renderMapChart(latestJson.data); } catch(e) { console.error('renderMapChart error:', e); }
        }
      } catch (err) {
        console.error('Failed to fetch telemetry:', err);
      }

      try {
        const diagRes = await fetch('/api/ai/diagnostics');
        const diagJson = await diagRes.json();
        if (diagJson) {
          try { renderDiagnostics(diagJson); } catch(e) { console.error('renderDiagnostics error:', e); }
        }
      } catch (err) {
        console.error('Failed to fetch diagnostics:', err);
      } finally {
        setTimeout(() => icon?.classList.remove('fa-spin'), 600);
      }
    }

    function renderKPIs(nodes) {
      const online = nodes.filter(n => n.status === 'ONLINE').length;
      const onlineEl = document.getElementById('stat-online-nodes');
      if (onlineEl) onlineEl.innerHTML = \`\${online} <span class="text-xs font-normal text-slate-400">/ \${nodes.length}</span>\`;
      
      const countEl = document.getElementById('active-nodes-count');
      if (countEl) countEl.innerText = \`\${online} / \${nodes.length} ONLINE\`;

      const latencies = nodes.filter(n => n.scrape_duration_ms > 0).map(n => n.scrape_duration_ms);
      if (latencies.length > 0) {
        const avgLat = Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length);
        const latEl = document.getElementById('stat-avg-latency');
        if (latEl) latEl.innerHTML = \`\${avgLat} <span class="text-xs font-normal text-slate-400">ms</span>\`;
      }

      const mems = nodes.filter(n => n.mem_usage_percent > 0).map(n => n.mem_usage_percent);
      if (mems.length > 0) {
        const avgMem = (mems.reduce((a, b) => a + b, 0) / mems.length).toFixed(1);
        const memEl = document.getElementById('stat-avg-mem');
        if (memEl) memEl.innerHTML = \`\${avgMem} <span class="text-xs font-normal text-slate-400">%</span>\`;
      }
    }

    function renderDiagnostics(diag) {
      const score = diag.fleet_health_score ?? 100;
      const pill = document.getElementById('ai-score-pill');
      const badge = document.getElementById('fleet-health-badge');

      if (pill) pill.innerText = \`HEALTH: \${score}%\`;
      if (badge) {
        badge.innerText = \`\${score}% \${diag.status || 'HEALTHY'}\`;
        badge.className = score >= 80 
          ? 'px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/60 font-semibold'
          : 'px-2 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800/60 font-semibold';
      }

      const list = document.getElementById('ai-diagnostics-list');
      if (list && diag.diagnostics && diag.diagnostics.length > 0) {
        list.innerHTML = diag.diagnostics.map(item => \`
          <div class="p-3 rounded-lg bg-slate-900/90 border border-slate-800 text-xs space-y-1">
            <div class="flex items-center justify-between text-cyan-400 font-mono font-semibold">
              <span><i class="fa-solid fa-shield-heart mr-1.5"></i>智能运维巡检</span>
              <span class="text-[10px] text-slate-500">AutoML Agent</span>
            </div>
            <p class="text-slate-300 leading-relaxed text-[11px]">\${item}</p>
          </div>
        \`).join('');
      }
    }

    function renderTable(nodes) {
      const tbody = document.getElementById('nodes-table-body');
      if (!tbody) return;

      tbody.innerHTML = nodes.map(n => \`
        <tr class="hover:bg-slate-800/40 transition">
          <td class="py-3 px-4 font-bold text-white flex items-center space-x-2">
            <span class="w-2 h-2 rounded-full \${n.status === 'ONLINE' ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]' : 'bg-rose-500'}"></span>
            <span>\${n.node_name}</span>
          </td>
          <td class="py-3 px-4 text-slate-400">\${n.provider || 'Cloud'} (\${n.region})</td>
          <td class="py-3 px-4 text-slate-300 font-mono">\${n.host_ip}</td>
          <td class="py-3 px-4">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold \${n.status === 'ONLINE' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/60' : 'bg-rose-950 text-rose-400 border border-rose-800/60'}">
              \${n.status}
            </span>
          </td>
          <td class="py-3 px-4">
            <div class="flex items-center space-x-2">
              <div class="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div class="bg-rose-400 h-full rounded-full" style="width: \${n.cpu_usage_percent || 0}%"></div>
              </div>
              <span>\${n.cpu_usage_percent || 0}%</span>
            </div>
          </td>
          <td class="py-3 px-4">
            <div class="flex items-center space-x-2">
              <div class="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div class="bg-cyan-400 h-full rounded-full" style="width: \${n.mem_usage_percent}%"></div>
              </div>
              <span>\${n.mem_usage_percent}%</span>
            </div>
          </td>
          <td class="py-3 px-4">
            <div class="flex items-center space-x-2">
              <div class="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div class="bg-indigo-400 h-full rounded-full" style="width: \${n.disk_usage_percent}%"></div>
              </div>
              <span>\${n.disk_usage_percent}%</span>
            </div>
          </td>
          <td class="py-3 px-4 font-mono font-semibold \${n.scrape_duration_ms < 50 ? 'text-emerald-400' : (n.scrape_duration_ms < 350 ? 'text-cyan-400' : 'text-amber-400')}">
            \${n.scrape_duration_ms} ms
          </td>
          <td class="py-3 px-4 text-slate-400 text-[11px]">
            \${n.recorded_at ? (n.recorded_at.includes('T') ? n.recorded_at.split('T')[1].slice(0, 8) : n.recorded_at.split(' ')[1]) : '刚刚'}
          </td>
        </tr>
      \`).join('');
    }

    function renderResourceChart(nodes) {
      if (!resourceChart) return;
      const names = nodes.map(n => n.node_name);
      const cpus = nodes.map(n => n.cpu_usage_percent || 0);
      const mems = nodes.map(n => n.mem_usage_percent);
      const disks = nodes.map(n => n.disk_usage_percent);

      resourceChart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { textStyle: { color: '#94a3b8' }, right: 10 },
        grid: { top: 35, bottom: 25, left: 40, right: 15 },
        xAxis: { type: 'category', data: names, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#cbd5e1', fontFamily: 'monospace' } },
        yAxis: { type: 'value', max: 100, splitLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#94a3b8', formatter: '{value}%' } },
        series: [
          { name: 'CPU', type: 'bar', data: cpus, itemStyle: { color: '#fb7185', borderRadius: [4, 4, 0, 0] } },
          { name: '内存', type: 'bar', data: mems, itemStyle: { color: '#06b6d4', borderRadius: [4, 4, 0, 0] } },
          { name: '磁盘', type: 'bar', data: disks, itemStyle: { color: '#8b5cf6', borderRadius: [4, 4, 0, 0] } }
        ]
      });
    }

    function renderLatencyChart(nodes) {
      if (!latencyChart) return;
      const sorted = [...nodes].sort((a, b) => a.scrape_duration_ms - b.scrape_duration_ms);
      const names = sorted.map(n => n.node_name);
      const latencies = sorted.map(n => n.scrape_duration_ms);

      latencyChart.setOption({
        tooltip: { trigger: 'axis', formatter: '{b}: {c} ms' },
        grid: { top: 20, bottom: 25, left: 45, right: 15 },
        xAxis: { type: 'category', data: names, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#cbd5e1', fontFamily: 'monospace' } },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#94a3b8', formatter: '{value}ms' } },
        series: [{
          type: 'line',
          smooth: true,
          data: latencies,
          symbolSize: 8,
          itemStyle: { color: '#38bdf8' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(56, 189, 248, 0.4)' },
              { offset: 1, color: 'rgba(56, 189, 248, 0.01)' }
            ])
          }
        }]
      });
    }

    function renderMapChart(nodes) {
      if (!mapChart) return;

      const regionGroups = {};
      nodes.forEach(n => {
        const region = n.region || 'unknown';
        if (!regionGroups[region]) regionGroups[region] = [];
        regionGroups[region].push(n);
      });

      const scatterData = [];
      Object.keys(regionGroups).forEach(region => {
        const group = regionGroups[region];
        // Use coordinates from backend, fallback if missing
        const centerLng = group[0].lng || 0;
        const centerLat = group[0].lat || 0;
        const count = group.length;

        group.forEach((n, idx) => {
          let lng = centerLng;
          let lat = centerLat;
          
          // If multiple nodes in same region, spread them in a circle
          if (count > 1) {
            const radius = 3.5; // Visually spread out by 3.5 degrees
            const angle = (2 * Math.PI * idx) / count - (Math.PI / 2); // Start at top
            lng += radius * Math.cos(angle);
            lat += radius * Math.sin(angle);
          }
          
          scatterData.push({
            name: n.node_name,
            value: [lng, lat, n.scrape_duration_ms, n.status, n.mem_usage_percent, n.region, n.cpu_usage_percent || 0]
          });
        });
      });

      mapChart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          formatter: function (params) {
            const d = params.value;
            return \`<div class="font-mono text-xs"><b>\${params.name}</b> (\${d[5]})<br/>状态: <span class="\${d[3] === 'ONLINE' ? 'text-emerald-400' : 'text-rose-400'}">\${d[3]}</span><br/>延迟: \${d[2]}ms<br/>CPU: \${d[6]}%<br/>内存: \${d[4]}%</div>\`;
          }
        },
        grid: { top: 30, bottom: 40, left: 50, right: 30 },
        xAxis: {
          type: 'value',
          min: -100,
          max: 160,
          splitLine: { lineStyle: { color: '#1e293b', type: 'dashed' } },
          axisLabel: { color: '#64748b', formatter: function(v) { return v > 0 ? v + '°E' : Math.abs(v) + '°W'; } }
        },
        yAxis: {
          type: 'value',
          min: -10,
          max: 60,
          splitLine: { lineStyle: { color: '#1e293b', type: 'dashed' } },
          axisLabel: { color: '#64748b', formatter: function(v) { return v + '°N'; } }
        },
        series: [
          {
            name: '全球节点',
            type: 'effectScatter',
            coordinateSystem: 'cartesian2d',
            data: scatterData,
            symbolSize: function (val) { return Math.max(14, 26 - val[2]/30); },
            showEffectOn: 'render',
            rippleEffect: { brushType: 'stroke', scale: 3 },
            label: {
              show: true,
              formatter: '{b}',
              position: 'top',
              color: '#38bdf8',
              fontFamily: 'monospace',
              fontWeight: 'bold',
              fontSize: 11
            },
            itemStyle: {
              color: function(params) {
                return params.value[3] === 'ONLINE' ? '#22d3ee' : '#f43f5e';
              },
              shadowBlur: 12,
              shadowColor: '#06b6d4'
            }
          }
        ]
      });
    }

    // Auth Helpers
    function toggleAuthModal() {
      const modal = document.getElementById('auth-modal');
      modal?.classList.toggle('hidden');
    }

    async function handleAuth(e) {
      e.preventDefault();
      const email = document.getElementById('auth-email').value;
      const password = document.getElementById('auth-password').value;
      const errorDiv = document.getElementById('auth-error');

      if (!supabaseClient) {
        errorDiv.innerText = 'Supabase client is not configured.';
        errorDiv.classList.remove('hidden');
        return;
      }

      try {
        const { data, error } = await supabaseClient.auth.signInWithPassword({ email, password });
        if (error) throw error;
        
        toggleAuthModal();
        checkUserSession();
      } catch (err) {
        errorDiv.innerText = err.message || 'Login failed';
        errorDiv.classList.remove('hidden');
      }
    }

    async function handleLogout() {
      if (supabaseClient) {
        await supabaseClient.auth.signOut();
        checkUserSession();
      }
    }

    async function checkUserSession() {
      if (!supabaseClient) return;
      try {
        const { data: { session } } = await supabaseClient.auth.getSession();
        const loginBtn = document.getElementById('login-btn');
        const userProfile = document.getElementById('user-profile');
        const userEmail = document.getElementById('user-email');

        if (session && session.user) {
          loginBtn?.classList.add('hidden');
          userProfile?.classList.remove('hidden');
          userProfile?.classList.add('flex');
          if (userEmail) userEmail.innerText = session.user.email;
        } else {
          loginBtn?.classList.remove('hidden');
          userProfile?.classList.add('hidden');
          userProfile?.classList.remove('flex');
        }
      } catch (e) {
        console.warn('Session check failed:', e);
      }
    }

    // Auto-refresh timer
    function startTimer() {
      setInterval(() => {
        countdown--;
        if (countdown <= 0) {
          countdown = 15;
          fetchData();
        }
        const timer = document.getElementById('sync-timer');
        if (timer) timer.innerText = \`Auto: \${countdown}s\`;
      }, 1000);
    }

    // Init lifecycle
    window.addEventListener('DOMContentLoaded', () => {
      initCharts();
      fetchData();
      checkUserSession();
      startTimer();
    });
  </script>
</body>
</html>`

  return c.html(html, 200, {
    'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
    'Pragma': 'no-cache'
  })
})

export default app

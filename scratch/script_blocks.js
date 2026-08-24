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
    const SUPABASE_URL = "https://qkpwuxaylvzycapkojvq.supabase.co";
    const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFrcHd1eGF5bHZ6eWNhcGtvanZxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM0MTI1NTksImV4cCI6MjA4ODk4ODU1OX0.iasxckoGYjRiLtaZcrmpwNW8QDuqh-BMGNy3rbmK4mQ";
    let supabase = null;

    try {
      if (typeof window.supabase !== 'undefined' && window.supabase.createClient && SUPABASE_URL && SUPABASE_KEY) {
        supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);
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
        console.log('API response:', latestJson);
        
        if (latestJson.status === 'success' && Array.isArray(latestJson.data)) {
          try { renderTable(latestJson.data); } catch(e) { console.error('renderTable error:', e); alert('renderTable error: ' + e.message); }
          try { renderKPIs(latestJson.data); } catch(e) { console.error('renderKPIs error:', e); alert('renderKPIs error: ' + e.message); }
          try { renderResourceChart(latestJson.data); } catch(e) { console.error('renderResourceChart error:', e); alert('renderResourceChart error: ' + e.message); }
          try { renderLatencyChart(latestJson.data); } catch(e) { console.error('renderLatencyChart error:', e); alert('renderLatencyChart error: ' + e.message); }
          try { renderMapChart(latestJson.data); } catch(e) { console.error('renderMapChart error:', e); alert('renderMapChart error: ' + e.message); }
        } else {
          console.error('Invalid response:', latestJson);
          alert('Invalid API response: ' + JSON.stringify(latestJson).substring(0, 200));
        }
      } catch (err) {
        console.error('Failed to fetch telemetry:', err);
        alert('Fetch error: ' + err.message);
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
      if (onlineEl) onlineEl.innerHTML = `${online} <span class="text-xs font-normal text-slate-400">/ ${nodes.length}</span>`;
      
      const countEl = document.getElementById('active-nodes-count');
      if (countEl) countEl.innerText = `${online} / ${nodes.length} ONLINE`;

      const latencies = nodes.filter(n => n.scrape_duration_ms > 0).map(n => n.scrape_duration_ms);
      if (latencies.length > 0) {
        const avgLat = Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length);
        const latEl = document.getElementById('stat-avg-latency');
        if (latEl) latEl.innerHTML = `${avgLat} <span class="text-xs font-normal text-slate-400">ms</span>`;
      }

      const mems = nodes.filter(n => n.mem_usage_percent > 0).map(n => n.mem_usage_percent);
      if (mems.length > 0) {
        const avgMem = (mems.reduce((a, b) => a + b, 0) / mems.length).toFixed(1);
        const memEl = document.getElementById('stat-avg-mem');
        if (memEl) memEl.innerHTML = `${avgMem} <span class="text-xs font-normal text-slate-400">%</span>`;
      }
    }

    function renderDiagnostics(diag) {
      const score = diag.fleet_health_score ?? 100;
      const pill = document.getElementById('ai-score-pill');
      const badge = document.getElementById('fleet-health-badge');

      if (pill) pill.innerText = `HEALTH: ${score}%`;
      if (badge) {
        badge.innerText = `${score}% ${diag.status || 'HEALTHY'}`;
        badge.className = score >= 80 
          ? 'px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/60 font-semibold'
          : 'px-2 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800/60 font-semibold';
      }

      const list = document.getElementById('ai-diagnostics-list');
      if (list && diag.diagnostics && diag.diagnostics.length > 0) {
        list.innerHTML = diag.diagnostics.map(item => `
          <div class="p-3 rounded-lg bg-slate-900/90 border border-slate-800 text-xs space-y-1">
            <div class="flex items-center justify-between text-cyan-400 font-mono font-semibold">
              <span><i class="fa-solid fa-shield-heart mr-1.5"></i>智能运维巡检</span>
              <span class="text-[10px] text-slate-500">AutoML Agent</span>
            </div>
            <p class="text-slate-300 leading-relaxed text-[11px]">${item}</p>
          </div>
        `).join('');
      }
    }

    function renderTable(nodes) {
      const tbody = document.getElementById('nodes-table-body');
      if (!tbody) return;

      tbody.innerHTML = nodes.map(n => `
        <tr class="hover:bg-slate-800/40 transition">
          <td class="py-3 px-4 font-bold text-white flex items-center space-x-2">
            <span class="w-2 h-2 rounded-full ${n.status === 'ONLINE' ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]' : 'bg-rose-500'}"></span>
            <span>${n.node_name}</span>
          </td>
          <td class="py-3 px-4 text-slate-400">${n.provider || 'Cloud'} (${n.region})</td>
          <td class="py-3 px-4 text-slate-300 font-mono">${n.host_ip}</td>
          <td class="py-3 px-4">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold ${n.status === 'ONLINE' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/60' : 'bg-rose-950 text-rose-400 border border-rose-800/60'}">
              ${n.status}
            </span>
          </td>
          <td class="py-3 px-4">
            <div class="flex items-center space-x-2">
              <div class="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div class="bg-cyan-400 h-full rounded-full" style="width: ${n.mem_usage_percent}%"></div>
              </div>
              <span>${n.mem_usage_percent}%</span>
            </div>
          </td>
          <td class="py-3 px-4">
            <div class="flex items-center space-x-2">
              <div class="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div class="bg-indigo-400 h-full rounded-full" style="width: ${n.disk_usage_percent}%"></div>
              </div>
              <span>${n.disk_usage_percent}%</span>
            </div>
          </td>
          <td class="py-3 px-4 font-mono font-semibold ${n.scrape_duration_ms < 50 ? 'text-emerald-400' : (n.scrape_duration_ms < 350 ? 'text-cyan-400' : 'text-amber-400')}">
            ${n.scrape_duration_ms} ms
          </td>
          <td class="py-3 px-4 text-slate-400 text-[11px]">
            ${n.recorded_at ? (n.recorded_at.includes('T') ? n.recorded_at.split('T')[1].slice(0, 8) : n.recorded_at.split(' ')[1]) : '刚刚'}
          </td>
        </tr>
      `).join('');
    }

    function renderResourceChart(nodes) {
      if (!resourceChart) return;
      const names = nodes.map(n => n.node_name);
      const mems = nodes.map(n => n.mem_usage_percent);
      const disks = nodes.map(n => n.disk_usage_percent);

      resourceChart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { textStyle: { color: '#94a3b8' }, right: 10 },
        grid: { top: 35, bottom: 25, left: 40, right: 15 },
        xAxis: { type: 'category', data: names, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#cbd5e1', fontFamily: 'monospace' } },
        yAxis: { type: 'value', max: 100, splitLine: { lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#94a3b8', formatter: '{value}%' } },
        series: [
          { name: '内存占用', type: 'bar', data: mems, itemStyle: { color: '#06b6d4', borderRadius: [4, 4, 0, 0] } },
          { name: '磁盘占用', type: 'bar', data: disks, itemStyle: { color: '#8b5cf6', borderRadius: [4, 4, 0, 0] } }
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
      
      const coords = {
        'jpa': [139.65, 35.67],
        'jpb': [139.75, 35.68],
        'jpc': [139.85, 35.69],
        'jpd': [139.55, 35.66],
        'jpe': [139.45, 35.65],
        'usa': [-77.48, 39.04],
        'usb': [-77.58, 39.14],
        'usc': [-77.38, 38.94],
        'sga': [103.81, 1.35],
        'cna': [116.40, 39.90]
      };

      const scatterData = nodes.map(n => {
        const pos = coords[n.node_name] || [0, 0];
        return {
          name: n.node_name,
          value: [pos[0], pos[1], n.scrape_duration_ms, n.status, n.mem_usage_percent, n.region]
        };
      });

      mapChart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          formatter: function (params) {
            const d = params.value;
            return `<div class="font-mono text-xs"><b>${params.name}</b> (${d[5]})<br/>状态: <span class="text-emerald-400">${d[3]}</span><br/>延迟: ${d[2]}ms<br/>内存: ${d[4]}%</div>`;
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

      if (!supabase) {
        errorDiv.innerText = 'Supabase client is not configured.';
        errorDiv.classList.remove('hidden');
        return;
      }

      try {
        const { data, error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        
        toggleAuthModal();
        checkUserSession();
      } catch (err) {
        errorDiv.innerText = err.message || 'Login failed';
        errorDiv.classList.remove('hidden');
      }
    }

    async function handleLogout() {
      if (supabase) {
        await supabase.auth.signOut();
        checkUserSession();
      }
    }

    async function checkUserSession() {
      if (!supabase) return;
      try {
        const { data: { session } } = await supabase.auth.getSession();
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
        if (timer) timer.innerText = `Auto: ${countdown}s`;
      }, 1000);
    }

    // Init lifecycle
    window.addEventListener('DOMContentLoaded', () => {
      initCharts();
      fetchData();
      checkUserSession();
      startTimer();
    });

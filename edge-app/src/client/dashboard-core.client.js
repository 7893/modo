    const SUPABASE_URL = ${supabaseUrl};
    const SUPABASE_KEY = ${supabaseKey};
    const TOPOLOGY_HUB_NODE = ${topologyHubNode};
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
    let currentActiveCurtain = 'overview';
    let cachedNodesData = [];
    let cachedForecastData = {};

    // Helper: Convert UTC string to Clean Time without brackets or timezone text
    function formatCleanTime(utcStr) {
      if (!utcStr) return '刚刚';
      try {
        let dateStr = utcStr;
        if (!dateStr.endsWith('Z') && !dateStr.includes('+')) {
          dateStr += 'Z';
        }
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return utcStr;
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
      } catch (e) {
        return utcStr;
      }
    }

    // Live clock in top header
    function updateClock() {
      const el = document.getElementById('live-clock-badge');
      if (el) {
        const now = new Date();
        el.innerText = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
      }
    }

    // Master 6-Curtain Switcher Logic (Supabase Accordion Style)
    function handleCurtainClick(panelId) {
      if (currentActiveCurtain === panelId) return;
      currentActiveCurtain = panelId;

      const panels = ['overview', 'map', 'resource', 'latency', 'table', 'ai'];

      panels.forEach(id => {
        const panelEl = document.getElementById(`panel-${id}`);
        const expandedContent = document.getElementById(`content-${id}-expanded`);
        const collapsedContent = document.getElementById(`content-${id}-collapsed`);

        if (id === panelId) {
          panelEl?.classList.remove('curtain-collapsed');
          panelEl?.classList.add('curtain-expanded');
          expandedContent?.classList.remove('hidden');
          expandedContent?.classList.add('flex');
          collapsedContent?.classList.remove('flex');
          collapsedContent?.classList.add('hidden');
        } else {
          panelEl?.classList.remove('curtain-expanded');
          panelEl?.classList.add('curtain-collapsed');
          expandedContent?.classList.remove('flex');
          expandedContent?.classList.add('hidden');
          collapsedContent?.classList.remove('hidden');
          collapsedContent?.classList.add('flex');
        }
      });

      // Trigger chart resize on smooth accordion animation end
      setTimeout(() => {
        if (panelId === 'map') mapChart?.resize();
        if (panelId === 'resource') resourceChart?.resize();
        if (panelId === 'latency') latencyChart?.resize();
        if (panelId === 'ai') hourlyTrendChart?.resize();
      }, 300);
    }

    // Initialize Charts with Supabase Light Theme
    function initCharts() {
      if (typeof echarts === 'undefined') return;
      try {
        const mapEl = document.getElementById('world-map-chart');
        if (mapEl) mapChart = echarts.init(mapEl, 'dark');

        const resEl = document.getElementById('resource-bar-chart');
        if (resEl) resourceChart = echarts.init(resEl, 'dark');

        const latEl = document.getElementById('latency-chart');
        if (latEl) latencyChart = echarts.init(latEl, 'dark');

        const resizeCharts = debounce(() => {
          resourceChart?.resize();
          latencyChart?.resize();
          mapChart?.resize();
          hourlyTrendChart?.resize();
        }, 200);
        window.addEventListener('resize', resizeCharts);

        const observer = new ResizeObserver(resizeCharts);
        if (mapEl) observer.observe(mapEl);
        if (resEl) observer.observe(resEl);
        if (latEl) observer.observe(latEl);
        const trendEl = document.getElementById('hourly-trend-chart');
        if (trendEl) observer.observe(trendEl);
      } catch (e) {
        console.warn('Chart init error:', e);
      }
    }

    function debounce(callback, delay) {
      let timeoutId;
      return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => callback(...args), delay);
      };
    }

    let fetchInFlight = false;

    // Fetch a single aggregated dashboard snapshot from the backend proxy.
    async function fetchData() {
      if (fetchInFlight) return;
      fetchInFlight = true;
      const icon = document.getElementById('refresh-icon');
      icon?.classList.add('fa-spin');

      try {
        const overviewRes = await fetch(`/api/dashboard/overview?_t=${Date.now()}`);
        if (!overviewRes.ok) throw new Error(`Dashboard request failed: ${overviewRes.status}`);
        const overviewJson = await overviewRes.json();
        const components = overviewJson.data || {};
        const latestJson = components.nodes;
        const forecastJson = components.forecast;

        if (forecastJson?.status === 'success' && Array.isArray(forecastJson.data)) {
          cachedForecastData = {};
          forecastJson.data.forEach(item => { cachedForecastData[item.node_name] = item; });
        }

        if (latestJson?.status === 'success' && Array.isArray(latestJson.data)) {
          cachedNodesData = latestJson.data;
          try { renderTable(latestJson.data); } catch(e) { console.error('renderTable error:', e); }
          try { renderFleetSummary(latestJson.data); } catch(e) { console.error('renderFleetSummary error:', e); }
          try { renderKPIs(latestJson.data); } catch(e) { console.error('renderKPIs error:', e); }
          try { renderResourceChart(latestJson.data); } catch(e) { console.error('renderResourceChart error:', e); }
          try { renderLatencyChart(latestJson.data); } catch(e) { console.error('renderLatencyChart error:', e); }
          try { renderMapChart(latestJson.data); } catch(e) { console.error('renderMapChart error:', e); }
        }

        const diagJson = components.diagnostics;
        if (diagJson && diagJson.status !== 'error') {
          try { renderDiagnostics(diagJson); } catch(e) { console.error('renderDiagnostics error:', e); }
        }

        const anomalyJson = components.anomalies;
        if (anomalyJson?.status === 'success' && Array.isArray(anomalyJson.data)) {
          renderAnomalyTags(anomalyJson.data);
        }

        const heatwaveJson = components.heatwave;
        if (heatwaveJson?.status === 'success') renderHeatWaveStatus(heatwaveJson);

        const hourlyJson = components.hourly;
        if (hourlyJson?.status === 'success' && Array.isArray(hourlyJson.data)) {
          renderHourlyTrendChart(hourlyJson.data);
        }
      } catch (err) {
        console.error('Failed to fetch dashboard overview:', err);
      } finally {
        fetchInFlight = false;
        setTimeout(() => icon?.classList.remove('fa-spin'), 600);
      }
    }

    function createSummaryElement(tag, className, text) {
      const element = document.createElement(tag);
      element.className = className;
      element.textContent = text;
      return element;
    }

    function renderFleetSummary(nodes) {
      const online = nodes.filter(node => node.status === 'ONLINE').length;
      const allOnline = nodes.length > 0 && online === nodes.length;
      const fleetStatus = document.getElementById('fleet-status');
      if (fleetStatus) {
        const dotClass = allOnline ? 'bg-emerald-500' : 'bg-amber-500';
        const dot = createSummaryElement('span', `w-2.5 h-2.5 rounded-full ${dotClass}`, '');
        const label = createSummaryElement('span', '', `${online} / ${nodes.length} 节点在线`);
        fleetStatus.replaceChildren(dot, label);
      }

      const regionGroups = new Map();
      nodes.forEach(node => {
        const region = node.region || '未指定区域';
        if (!regionGroups.has(region)) regionGroups.set(region, []);
        regionGroups.get(region).push(node);
      });

      const fleetCount = document.getElementById('fleet-node-count');
      if (fleetCount) fleetCount.textContent = `${nodes.length} 台主机 · ${regionGroups.size} 个区域`;

      const overview = document.getElementById('overview-region-list');
      if (overview) {
        const cards = [...regionGroups.entries()].map(([region, regionNodes]) => {
          const onlineCount = regionNodes.filter(node => node.status === 'ONLINE').length;
          const providers = [...new Set(regionNodes.map(node => node.provider || 'Cloud'))].join(' · ');
          const card = createSummaryElement('div', 'p-2.5 rounded-xl bg-slate-900/70 border border-slate-800/80 flex items-center justify-between font-mono text-xs shadow-xs', '');
          const identity = createSummaryElement('div', '', '');
          identity.append(
            createSummaryElement('div', 'font-bold text-white', `${region} · ${regionNodes.length} 台`),
            createSummaryElement('div', 'text-[10px] text-slate-500', providers)
          );
          card.append(identity, createSummaryElement('span', 'text-emerald-300 font-bold text-[10px]', `${onlineCount} ONLINE`));
          return card;
        });
        overview.replaceChildren(...cards);
      }

      const mapSummary = document.getElementById('map-region-summary');
      if (mapSummary) {
        const badges = [...regionGroups.entries()].map(([region, regionNodes]) =>
          createSummaryElement('span', 'px-2.5 py-0.5 rounded-lg bg-slate-900/90 border border-slate-800 text-slate-300 shadow-xs', `${region} (${regionNodes.length})`)
        );
        mapSummary.replaceChildren(...badges);
      }
    }

    function renderKPIs(nodes) {
      const online = nodes.filter(n => n.status === 'ONLINE').length;
      const onlineEl = document.getElementById('stat-online-nodes');
      if (onlineEl) onlineEl.innerHTML = `${online} <span class="text-xs font-normal text-slate-400">/ ${nodes.length}</span>`;

      const countEl = document.getElementById('active-nodes-count');
      if (countEl) countEl.innerText = `${online} / ${nodes.length} ONLINE`;

      // Real-time dynamic DB record count from latest ingested telemetry ID
      const recordIds = nodes.map(n => parseInt(n.id, 10)).filter(id => !isNaN(id) && id > 0);
      if (recordIds.length > 0) {
        const maxRecordId = Math.max(...recordIds);
        const formatted = `${maxRecordId.toLocaleString()} 条`;

        const totalDbEl = document.getElementById('total-db-records');
        if (totalDbEl) totalDbEl.innerText = formatted;

        const kpiDbEl = document.getElementById('kpi-db-records');
        if (kpiDbEl) kpiDbEl.innerText = formatted;
      }

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
        const resMemEl = document.getElementById('res-avg-mem');
        if (resMemEl) resMemEl.innerText = `${avgMem}%`;
      }

      const sortedCpu = [...nodes].sort((a, b) => (b.cpu_usage_percent || 0) - (a.cpu_usage_percent || 0));
      if (sortedCpu.length > 0) {
        const peakCpuEl = document.getElementById('res-peak-cpu');
        if (peakCpuEl) peakCpuEl.innerText = `${sortedCpu[0].node_name} (${sortedCpu[0].cpu_usage_percent || 0}%)`;
      }

      const disks = nodes.filter(n => n.disk_usage_percent > 0).map(n => n.disk_usage_percent);
      if (disks.length > 0) {
        const avgDisk = (disks.reduce((a, b) => a + b, 0) / disks.length).toFixed(1);
        const resDiskEl = document.getElementById('res-avg-disk');
        if (resDiskEl) resDiskEl.innerText = `${avgDisk}% (正常)`;
      }
    }

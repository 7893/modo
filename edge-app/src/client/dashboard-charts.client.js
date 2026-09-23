    function renderTable(nodes) {
      const fleetBadge = document.getElementById('table-fleet-badge');
      if (fleetBadge) {
        const onlineCount = nodes.filter(n => n.status === 'ONLINE').length;
        if (onlineCount === nodes.length) {
          fleetBadge.innerHTML = `<i class="fa-solid fa-server text-emerald-400"></i><span>共 ${nodes.length} 台主机 (全部正常)</span>`;
          fleetBadge.className = "px-3.5 py-1 rounded-full bg-slate-900/90 border border-slate-700 text-xs font-mono text-slate-200 font-bold flex items-center gap-1.5 shadow-sm";
        } else {
          fleetBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-amber-400"></i><span>${onlineCount} / ${nodes.length} 台在线 (${nodes.length - onlineCount} 异常)</span>`;
          fleetBadge.className = "px-3.5 py-1 rounded-full bg-amber-950/80 border border-amber-800 text-xs font-mono text-amber-300 font-bold flex items-center gap-1.5 shadow-sm";
        }
      }

      const tbody = document.getElementById('nodes-table-body');
      if (!tbody) return;

      tbody.innerHTML = nodes.map(n => `
        <tr class="hover:bg-slate-800/60 transition border-b border-slate-800/40">
          <td class="py-2 px-3.5 font-bold text-white flex items-center space-x-2">
            <span class="w-2.5 h-2.5 rounded-full ${n.status === 'ONLINE' ? 'bg-emerald-500 shadow-[0_0_6px_#10b981]' : 'bg-rose-500'}"></span>
            <span class="text-xs lg:text-sm">${n.node_name}</span>
          </td>
          <td class="py-2 px-3.5 text-slate-400">${n.provider || 'Cloud'} (${n.region})</td>
          <td class="py-2 px-3.5 text-slate-400 font-mono"><span class="px-2 py-0.5 rounded-md bg-slate-900 border border-slate-800 text-slate-300 text-[11px] inline-flex items-center gap-1.5 shadow-xs"><i class="fa-solid fa-lock text-[10px] text-emerald-400"></i><span>QUIC 隧道 (隐藏)</span></span></td>
          <td class="py-2 px-3.5">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${n.status === 'ONLINE' ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800' : 'bg-rose-950/70 text-rose-300 border border-rose-800'}">
              ${n.status}
            </span>
          </td>
          <td class="py-2 px-3.5">
            <div class="flex items-center space-x-2">
              <div class="w-16 lg:w-20 bg-slate-800 rounded-full h-2 overflow-hidden border border-slate-700">
                <div class="bg-rose-500 h-full rounded-full" style="width: ${n.cpu_usage_percent || 0}%"></div>
              </div>
              <span class="font-semibold text-slate-200">${n.cpu_usage_percent || 0}%</span>
            </div>
          </td>
          <td class="py-2 px-3.5">
            <div class="flex items-center space-x-2">
              <div class="w-16 lg:w-20 bg-slate-800 rounded-full h-2 overflow-hidden border border-slate-700">
                <div class="bg-emerald-500 h-full rounded-full" style="width: ${n.mem_usage_percent}%"></div>
              </div>
              <span class="font-semibold text-slate-200">${n.mem_usage_percent}%</span>
            </div>
          </td>
          <td class="py-2 px-3.5">
            <div class="flex items-center space-x-2">
              <div class="w-16 lg:w-20 bg-slate-800 rounded-full h-2 overflow-hidden border border-slate-700">
                <div class="bg-amber-500 h-full rounded-full" style="width: ${n.disk_usage_percent}%"></div>
              </div>
              <span class="font-semibold text-slate-200">${n.disk_usage_percent}%</span>
            </div>
          </td>
          <td class="py-2 px-3.5 font-mono font-semibold ${n.scrape_duration_ms < 50 ? 'text-emerald-400' : (n.scrape_duration_ms < 350 ? 'text-blue-400' : 'text-amber-400')}">
            ${n.scrape_duration_ms} ms
          </td>
          <td class="py-2 px-3.5 text-slate-500 text-xs font-mono">
            ${formatCleanTime(n.recorded_at)}
          </td>
        </tr>
      `).join('');
    }

    function renderResourceChart(nodes) {
      if (!resourceChart) return;
      const names = nodes.map(n => n.node_name);
      const cpus = nodes.map(n => n.cpu_usage_percent || 0);
      const mems = nodes.map(n => n.mem_usage_percent);
      const disks = nodes.map(n => n.disk_usage_percent);

      resourceChart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { textStyle: { color: '#94A3B8' }, right: 15, top: 5 },
        grid: { top: 35, bottom: 25, left: 45, right: 15 },
        xAxis: { type: 'category', data: names, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94A3B8', fontFamily: 'monospace', fontSize: 11 } },
        yAxis: { type: 'value', max: 100, splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.06)' } }, axisLabel: { color: '#94A3B8', formatter: '{value}%' } },
        series: [
          { name: 'CPU', type: 'bar', data: cpus, itemStyle: { color: '#E11D48', borderRadius: [4, 4, 0, 0] } },
          { name: '内存', type: 'bar', data: mems, itemStyle: { color: '#10B981', borderRadius: [4, 4, 0, 0] } },
          { name: '磁盘', type: 'bar', data: disks, itemStyle: { color: '#F59E0B', borderRadius: [4, 4, 0, 0] } }
        ]
      });
    }

    function renderLatencyChart(nodes) {
      if (!latencyChart) return;
      const sorted = [...nodes].sort((a, b) => a.scrape_duration_ms - b.scrape_duration_ms);
      const names = sorted.map(n => n.node_name);
      const latencies = sorted.map(n => n.scrape_duration_ms);

      // Dynamic tier calculation based on actual latency distribution
      const tier1 = sorted.filter(n => n.scrape_duration_ms < 50);
      const tier2 = sorted.filter(n => n.scrape_duration_ms >= 50 && n.scrape_duration_ms < 300);
      const tier3 = sorted.filter(n => n.scrape_duration_ms >= 300);

      const fmtRange = arr => arr.length
        ? `${Math.min(...arr.map(n=>n.scrape_duration_ms))}~${Math.max(...arr.map(n=>n.scrape_duration_ms))}ms`
        : '--';
      const fmtNames = arr => arr.map(n => n.node_name).join(' · ') || '--';

      const t1l = document.getElementById('tier1-label');
      const t2l = document.getElementById('tier2-label');
      const t3l = document.getElementById('tier3-label');
      const t1n = document.getElementById('tier1-nodes');
      const t2n = document.getElementById('tier2-nodes');
      const t3n = document.getElementById('tier3-nodes');

      if (t1l) t1l.innerHTML = `<span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>第一梯队 (${tier1.length ? fmtRange(tier1) : '<50ms'})`;
      if (t2l) t2l.innerHTML = `<span class="w-2.5 h-2.5 rounded-full bg-blue-500"></span>第二梯队 (${tier2.length ? fmtRange(tier2) : '50~300ms'})`;
      if (t3l) t3l.innerHTML = `<span class="w-2.5 h-2.5 rounded-full bg-amber-500"></span>第三梯队 (${tier3.length ? fmtRange(tier3) : '300ms+'})`;
      if (t1n) t1n.innerText = fmtNames(tier1);
      if (t2n) t2n.innerText = fmtNames(tier2);
      if (t3n) t3n.innerText = fmtNames(tier3);

      latencyChart.setOption({
        tooltip: { trigger: 'axis', formatter: '{b}: {c} ms' },
        grid: { top: 30, bottom: 25, left: 50, right: 20 },
        xAxis: { type: 'category', data: names, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94A3B8', fontFamily: 'monospace', fontSize: 11 } },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.06)' } }, axisLabel: { color: '#94A3B8', formatter: '{value}ms' } },
        series: [{
          name: '探测延迟',
          type: 'line',
          smooth: true,
          data: latencies,
          symbolSize: 8,
          itemStyle: { color: '#7C3AED' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(124, 58, 237, 0.25)' },
              { offset: 1, color: 'rgba(124, 58, 237, 0.01)' }
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
      const nodeCoords = {};

      Object.keys(regionGroups).forEach(region => {
        const group = regionGroups[region];
        const centerLng = group[0].lng || 0;
        const centerLat = group[0].lat || 0;
        const count = group.length;

        group.forEach((n, idx) => {
          let lng = centerLng;
          let lat = centerLat;

          if (count > 1) {
            const radius = 5.5;
            const angle = (2 * Math.PI * idx) / count - (Math.PI / 2);
            lng += radius * Math.cos(angle);
            lat += radius * Math.sin(angle);
          }

          nodeCoords[n.node_name] = [lng, lat];
          scatterData.push({
            name: n.node_name,
            value: [lng, lat, n.scrape_duration_ms, n.status, n.mem_usage_percent, n.region, n.cpu_usage_percent || 0, n.disk_usage_percent || 0]
          });
        });
      });

      const linesData = [];
      const hubName = nodeCoords[TOPOLOGY_HUB_NODE]
        ? TOPOLOGY_HUB_NODE
        : nodes[0]?.node_name;
      const hubCoord = hubName ? nodeCoords[hubName] : null;
      if (hubCoord) {
        nodes.forEach(n => {
          if (n.node_name !== hubName && nodeCoords[n.node_name]) {
            // Use forecast period if available, fallback to realtime scrape_duration_ms
            const forecast = cachedForecastData[n.node_name];
            let period;
            if (forecast && forecast.period) {
              period = forecast.period;
            } else {
              // Fallback: log-scale mapping from actual scrape_duration_ms
              const ms = Math.max(10, Math.min(1000, n.scrape_duration_ms || 200));
              period = Math.round((1.0 + (Math.log10(ms) / Math.log10(1000)) * 14) * 10) / 10;
            }
            linesData.push({
              fromName: `${n.node_name} (${n.region})`,
              toName: `${hubName} (拓扑中枢)`,
              coords: [nodeCoords[n.node_name], hubCoord],
              period: period,
              predictedMs: forecast ? forecast.predicted_ms : n.scrape_duration_ms,
              mlAvailable: forecast ? forecast.ml_available : false
            });
          }
        });
      }

      mapChart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'item',
          backgroundColor: 'rgba(11, 18, 34, 0.96)',
          borderColor: 'rgba(56, 189, 248, 0.45)',
          borderWidth: 1,
          padding: [10, 14],
          extraCssText: 'box-shadow: 0 16px 36px -4px rgba(0, 0, 0, 0.9), 0 0 16px rgba(56, 189, 248, 0.2); border-radius: 12px; backdrop-filter: blur(12px); pointer-events: none;',
          formatter: function (params) {
            if (params.seriesType === 'lines') {
              return `
                <div style="font-family: 'JetBrains Mono', monospace; min-width: 170px; line-height: 1.5;">
                  <div style="color: #38BDF8; font-size: 11px; font-weight: 600; margin-bottom: 5px; display: flex; align-items: center; gap: 6px;">
                    <i class="fa-solid fa-satellite-dish"></i> 遥测上报链路
                  </div>
                  <div style="color: #F1F5F9; font-size: 12px; font-weight: 700;">
                    ${params.data.fromName}
                  </div>
                  <div style="color: #64748B; font-size: 11px; margin: 3px 0;">
                    &darr; 汇聚至中枢
                  </div>
                  <div style="color: #C084FC; font-size: 12px; font-weight: 700;">
                    ${params.data.toName}
                  </div>
                  <div style="margin-top: 6px; padding-top: 5px; border-top: 1px solid rgba(51,65,85,0.5); font-size: 11px; color: #94A3B8;">
                    ${params.data.mlAvailable
                      ? `<span style="color:#34D399">▸ ML预测:</span> <b style="color:#fff">${params.data.predictedMs}ms</b> · period ${params.data.period}s`
                      : `<span style="color:#FBBF24">▸ EMA估算:</span> <b style="color:#fff">${params.data.predictedMs}ms</b>`
                    }
                  </div>
                </div>
              `;
            }
            const d = params.value;
            const isHub = params.name === hubName;
            const status = d[3] || 'ONLINE';
            const isOnline = status === 'ONLINE';
            const lat = d[2];
            const latColor = lat < 50 ? '#34D399' : (lat < 300 ? '#38BDF8' : '#FBBF24');

            return `
              <div style="font-family: 'JetBrains Mono', -apple-system, sans-serif; min-width: 195px; line-height: 1.5;">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; padding-bottom: 6px; border-bottom: 1px solid rgba(51, 65, 85, 0.6);">
                  <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="color: #FFFFFF; font-size: 13px; font-weight: 800; letter-spacing: -0.01em;">${params.name}</span>
                    ${isHub ? '<span style="background: rgba(168, 85, 247, 0.2); color: #C084FC; border: 1px solid rgba(168, 85, 247, 0.5); font-size: 10px; padding: 1px 5px; border-radius: 4px; font-weight: 700;">数据中枢</span>' : ''}
                  </div>
                  <span style="color: #94A3B8; font-size: 11px; font-weight: 500;">${d[5]}</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 4px; font-size: 11.5px;">
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #94A3B8;">集群状态:</span>
                    <span style="color: ${isOnline ? '#34D399' : '#F43F5E'}; font-weight: 700; display: flex; align-items: center; gap: 5px;">
                      <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: ${isOnline ? '#10B981' : '#F43F5E'};"></span>
                      ${status}
                    </span>
                  </div>
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #94A3B8;">遥测延迟:</span>
                    <span style="color: ${latColor}; font-weight: 700;">${lat} ms</span>
                  </div>
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #94A3B8;">CPU 利用率:</span>
                    <span style="color: #FB7185; font-weight: 700;">${d[6]}%</span>
                  </div>
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #94A3B8;">内存占用:</span>
                    <span style="color: #34D399; font-weight: 700;">${d[4]}%</span>
                  </div>
                  ${d[7] !== undefined ? `
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #94A3B8;">磁盘空间:</span>
                    <span style="color: #FBBF24; font-weight: 700;">${d[7]}%</span>
                  </div>` : ''}
                </div>
                <div style="color: #64748B; font-size: 10.5px; margin-top: 6px; padding-top: 5px; border-top: 1px dashed rgba(51, 65, 85, 0.5); display: flex; align-items: center; justify-content: space-between;">
                  <span style="color: #64748B;">网络接入:</span>
                  <span style="color: #38BDF8; font-weight: 500; display: inline-flex; align-items: center; gap: 4px;">
                    <i class="fa-solid fa-lock" style="font-size: 9px; color: #34D399;"></i>QUIC 隧道 (隐藏)
                  </span>
                </div>
              </div>
            `;
          }
        },
        grid: { top: 30, bottom: 40, left: 50, right: 30 },
        xAxis: {
          type: 'value',
          min: -115,
          max: 165,
          splitLine: { lineStyle: { color: 'rgba(59, 130, 246, 0.15)', type: 'dashed' } },
          axisLabel: { color: '#94A3B8', formatter: function(v) { return v > 0 ? v + '°E' : Math.abs(v) + '°W'; } }
        },
        yAxis: {
          type: 'value',
          min: -15,
          max: 65,
          splitLine: { lineStyle: { color: 'rgba(59, 130, 246, 0.15)', type: 'dashed' } },
          axisLabel: { color: '#94A3B8', formatter: function(v) { return v + '°N'; } }
        },
        series: [
          // One series per line so each arrow has its own period
          ...linesData.map(line => ({
            name: '遥测链路',
            type: 'lines',
            coordinateSystem: 'cartesian2d',
            zlevel: 1,
            effect: {
              show: true,
              period: line.period,
              trailLength: 0.25,
              symbol: 'arrow',
              symbolSize: 4,
              color: '#38BDF8'
            },
            lineStyle: {
              color: 'rgba(56, 189, 248, 0.22)',
              width: 1.2,
              curveness: 0.18
            },
            data: [line]
          })),
          {
            name: '集群节点',
            type: 'effectScatter',
            coordinateSystem: 'cartesian2d',
            zlevel: 2,
            data: scatterData,
            symbolSize: function (val, params) {
              if (params.name === hubName) return 22;
              return Math.max(14, 26 - val[2]/30);
            },
            showEffectOn: 'render',
            rippleEffect: { brushType: 'stroke', scale: 3.5 },
            label: {
              show: true,
              formatter: '{b}',
              position: 'top',
              color: function(params) {
                return params.name === hubName ? '#C084FC' : '#93C5FD';
              },
              fontFamily: 'monospace',
              fontWeight: 'bold',
              fontSize: 11
            },
            itemStyle: {
              color: function(params) {
                if (params.name === hubName) return '#A855F7';
                return params.value[3] === 'ONLINE' ? '#38BDF8' : '#F43F5E';
              },
              shadowBlur: 12,
              shadowColor: function(params) {
                return params.name === hubName ? 'rgba(168, 85, 247, 0.7)' : 'rgba(56, 189, 248, 0.5)';
              }
            }
          }
        ]
      });
    }

    // Auth Helpers

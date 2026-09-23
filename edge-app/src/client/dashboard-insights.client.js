    function renderDiagnostics(diag) {
      const score = diag.fleet_health_score ?? 100;
      const pill = document.getElementById('ai-score-pill');
      const badge = document.getElementById('fleet-health-badge');

      const status = diag.status || 'HEALTHY';
      if (pill) {
        pill.innerText = `HEALTH: ${score}%`;
        pill.className = status === 'HEALTHY'
          ? 'px-4 py-1.5 rounded-full text-xs font-mono font-extrabold bg-slate-900/90 text-emerald-300 border border-emerald-800 shadow-sm'
          : status === 'WARNING'
          ? 'px-4 py-1.5 rounded-full text-xs font-mono font-extrabold bg-slate-900/90 text-amber-300 border border-amber-800 shadow-sm'
          : 'px-4 py-1.5 rounded-full text-xs font-mono font-extrabold bg-slate-900/90 text-rose-300 border border-rose-800 shadow-sm';
      }
      if (badge) {
        badge.innerText = `${score}% ${status}`;
        badge.className = status === 'HEALTHY'
          ? 'px-2.5 py-0.5 rounded-full bg-emerald-950/60 text-emerald-300 border border-emerald-800 font-semibold text-[11px]'
          : status === 'WARNING'
          ? 'px-2.5 py-0.5 rounded-full bg-amber-950/60 text-amber-300 border border-amber-800 font-semibold text-[11px]'
          : 'px-2.5 py-0.5 rounded-full bg-rose-950/60 text-rose-300 border border-rose-800 font-semibold text-[11px]';
      }

      // Update anomaly count badge
      const anomalyBadge = document.getElementById('anomaly-count-badge');
      if (anomalyBadge) {
        const count = diag.anomalies_count || 0;
        anomalyBadge.innerText = `${count} 告警`;
        anomalyBadge.className = status === 'CRITICAL'
          ? 'text-[10px] text-rose-300 px-2 py-0.5 rounded-full bg-rose-950/80 border border-rose-800 font-bold'
          : count > 0
          ? 'text-[10px] text-amber-300 px-2 py-0.5 rounded-full bg-amber-950/80 border border-amber-800 font-bold'
          : 'text-[10px] text-slate-300 px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 font-bold';
      }

      // Update HeatWave stats from diagnostics
      if (diag.heatwave) {
        const hwQueriesEl = document.getElementById('hw-queries-offloaded');
        const hwRecordsEl = document.getElementById('hw-total-records');
        if (hwQueriesEl) hwQueriesEl.innerText = diag.heatwave.queries_offloaded || '--';
        if (hwRecordsEl) hwRecordsEl.innerText = (diag.heatwave.total_records || 0).toLocaleString();
      }

      // Update footer: evaluated_at and status
      const diagTime = document.getElementById('diag-evaluated-at');
      if (diagTime && diag.evaluated_at) {
        const d = new Date(diag.evaluated_at + 'Z');
        diagTime.innerText = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
      }
      const diagFooter = document.getElementById('diag-footer-status');
      if (diagFooter) {
        const s = diag.status || 'HEALTHY';
        const cfg = {
          HEALTHY:  { cls: 'text-emerald-400', icon: 'fa-circle-check',    txt: '巡检正常' },
          WARNING:  { cls: 'text-amber-400',   icon: 'fa-triangle-exclamation', txt: '存在告警' },
          CRITICAL: { cls: 'text-rose-400',    icon: 'fa-circle-exclamation',   txt: '需要介入' }
        }[s] || { cls: 'text-emerald-400', icon: 'fa-circle-check', txt: '巡检正常' };
        diagFooter.className = `${cfg.cls} flex items-center font-bold`;
        diagFooter.innerHTML = `<i class="fa-solid ${cfg.icon} mr-1"></i>${cfg.txt}`;
      }

      const list = document.getElementById('ai-diagnostics-list');
      if (list && diag.diagnostics && diag.diagnostics.length > 0) {
        const featurePipelineHtml = `
          <div class="p-2.5 rounded-xl bg-slate-900/70 border border-emerald-500/20 text-xs space-y-1.5 mb-2">
            <div class="flex items-center justify-between text-[10px] font-mono">
              <span class="text-emerald-400 font-bold"><i class="fa-solid fa-check-circle mr-1"></i>AutoML 特征流水线就绪</span>
              <span class="text-slate-400">v_telemetry_ml_features</span>
            </div>
            <div class="grid grid-cols-3 gap-1.5 text-[10px] font-mono text-center">
              <div class="p-1 rounded bg-slate-800/80 text-slate-300">空值率: <span class="text-emerald-400 font-bold">0%</span></div>
              <div class="p-1 rounded bg-slate-800/80 text-slate-300">特征: <span class="text-blue-400 font-bold">6 维标量</span></div>
              <div class="p-1 rounded bg-slate-800/80 text-slate-300">规范: <span class="text-amber-400 font-bold">英文分词</span></div>
            </div>
          </div>
        `;
        list.innerHTML = featurePipelineHtml + diag.diagnostics.map((item, idx) => {
          let iconClass = 'fa-circle-check text-emerald-400';
          let borderClass = 'border-emerald-500/20';
          if (item.includes('🔴') || item.includes('CRITICAL')) {
            iconClass = 'fa-circle-xmark text-rose-400';
            borderClass = 'border-rose-500/30';
          } else if (item.includes('🟡') || item.includes('告警') || item.includes('WARNING') || item.includes('LATENCY_SURGE') || item.includes('CPU_SPIKE') || item.includes('TIMEOUT') || item.includes('OFFLINE')) {
            iconClass = 'fa-triangle-exclamation text-amber-400';
            borderClass = 'border-amber-500/30';
          } else if (item.includes('HTAP') || item.includes('HeatWave')) {
            iconClass = 'fa-brain text-purple-400';
            borderClass = 'border-purple-500/20';
          }
          return `
            <div class="p-2.5 rounded-lg bg-slate-900/70 border ${borderClass} text-[11px] shadow-xs mb-1.5">
              <p class="text-slate-200 leading-relaxed"><i class="fa-solid ${iconClass} mr-1.5"></i>${item}</p>
            </div>
          `;
        }).join('');
      }
    }

    function renderAnomalyTags(anomalies) {
      const tagsContainer = document.getElementById('ai-anomaly-tags');
      if (!tagsContainer) return;
      if (!anomalies || anomalies.length === 0) {
        tagsContainer.innerHTML = `<span class="text-[10px] text-emerald-400 font-mono"><i class="fa-solid fa-check mr-1"></i>当前无未恢复异常</span>`;
        return;
      }
      tagsContainer.innerHTML = anomalies.slice(0, 4).map(a => {
        const isCritical = a.severity === 'CRITICAL';
        const isHigh = a.severity === 'HIGH';
        const isMedium = a.severity === 'MEDIUM';
        const colorClass = isCritical
          ? 'bg-rose-950/80 text-rose-300 border-rose-800'
          : isHigh
          ? 'bg-amber-950/80 text-amber-300 border-amber-800'
          : isMedium
          ? 'bg-yellow-950/60 text-yellow-300 border-yellow-800'
          : 'bg-blue-950/60 text-blue-300 border-blue-800';
        return `<span class="px-2 py-0.5 rounded-md border text-[10px] font-mono font-semibold ${colorClass}">
          ${a.anomaly_type} (${a.open_count || a.count}) · ${a.severity}
        </span>`;
      }).join('');
    }

    function renderHeatWaveStatus(data) {
      // Cluster status
      const statusEl = document.getElementById('hw-cluster-status');
      if (statusEl) {
        const isOnline = data.cluster?.service === 'ONLINE';
        statusEl.innerText = isOnline ? 'ONLINE' : 'OFFLINE';
        statusEl.className = isOnline
          ? 'text-[10px] text-emerald-300 px-2 py-0.5 rounded-full bg-emerald-950/80 border border-emerald-800 font-bold'
          : 'text-[10px] text-rose-300 px-2 py-0.5 rounded-full bg-rose-950/80 border border-rose-800 font-bold';
      }

      // Memory
      const memUsedEl = document.getElementById('hw-memory-used');
      const memPctEl = document.getElementById('hw-memory-pct');
      if (memUsedEl) memUsedEl.innerText = `${data.memory?.used_mb || 0} MB`;
      if (memPctEl) memPctEl.innerText = `${data.memory?.usage_percent || 0}%`;

      // Queries
      const queriesEl = document.getElementById('hw-queries-offloaded');
      const offloadRateEl = document.getElementById('hw-offload-rate');
      if (queriesEl) queriesEl.innerText = data.performance?.queries_offloaded || 0;
      if (offloadRateEl) offloadRateEl.innerText = `${data.performance?.offload_rate_percent || 0}%`;

      // Tables & Records
      const tablesEl = document.getElementById('hw-tables-loaded');
      const recordsEl = document.getElementById('hw-total-records');
      if (tablesEl) tablesEl.innerText = data.data?.tables_loaded || 0;
      if (recordsEl) recordsEl.innerText = (data.data?.total_records || 0).toLocaleString();

      // ML & CP status
      const mlEl = document.getElementById('hw-ml-status');
      const cpEl = document.getElementById('hw-cp-status');
      if (mlEl) mlEl.innerText = data.cluster?.ml_status || 'OFF';
      if (cpEl) cpEl.innerText = data.cluster?.change_propagation || 'OFF';
    }

    let hourlyTrendChart = null;
    function renderHourlyTrendChart(hourlyData) {
      const chartEl = document.getElementById('hourly-trend-chart');
      if (!chartEl) return;

      if (!hourlyTrendChart) {
        hourlyTrendChart = echarts.init(chartEl);
      }

      // Group by hour and calculate averages across all nodes
      const hourMap = {};
      hourlyData.forEach(item => {
        const hour = item.hour;
        if (!hourMap[hour]) {
          hourMap[hour] = { cpuSum: 0, memSum: 0, latSum: 0, count: 0 };
        }
        hourMap[hour].cpuSum += parseFloat(item.avg_cpu) || 0;
        hourMap[hour].memSum += parseFloat(item.avg_mem) || 0;
        hourMap[hour].latSum += parseFloat(item.peak_latency) || 0;
        hourMap[hour].count += 1;
      });

      const hours = Object.keys(hourMap).sort().slice(-24);
      const avgCpus = hours.map(h => (hourMap[h].cpuSum / hourMap[h].count).toFixed(1));
      const avgMems = hours.map(h => (hourMap[h].memSum / hourMap[h].count).toFixed(1));
      const avgLats = hours.map(h => Math.round(hourMap[h].latSum / hourMap[h].count));
      const labels = hours.map(h => h.split(' ')[1]?.slice(0,5) || h.slice(11, 16));

      hourlyTrendChart.setOption({
        tooltip: {
          trigger: 'axis',
          formatter: function(params) {
            let tip = params[0].axisValue + '<br/>';
            params.forEach(p => {
              const unit = p.seriesName === 'Latency' ? 'ms' : '%';
              tip += `${p.marker} ${p.seriesName}: ${p.value}${unit}<br/>`;
            });
            return tip;
          }
        },
        legend: {
          data: ['CPU', 'Memory', 'Latency'],
          textStyle: { color: '#94A3B8', fontSize: 10 },
          top: 0,
          right: 5,
          itemWidth: 12,
          itemHeight: 8
        },
        grid: { top: 28, bottom: 22, left: 35, right: 45 },
        xAxis: {
          type: 'category',
          data: labels,
          axisLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#94A3B8', fontSize: 9 },
          boundaryGap: false
        },
        yAxis: [
          {
            type: 'value',
            max: 100,
            splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.06)' } },
            axisLabel: { color: '#94A3B8', formatter: '{value}%', fontSize: 9 }
          },
          {
            type: 'value',
            position: 'right',
            splitLine: { show: false },
            axisLabel: { color: '#94A3B8', formatter: '{value}ms', fontSize: 9 }
          }
        ],
        series: [
          {
            name: 'CPU',
            type: 'line',
            smooth: true,
            data: avgCpus,
            symbol: 'none',
            itemStyle: { color: '#F59E0B' },
            lineStyle: { width: 2 },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(245, 158, 11, 0.25)' },
                { offset: 1, color: 'rgba(245, 158, 11, 0.02)' }
              ])
            }
          },
          {
            name: 'Memory',
            type: 'line',
            smooth: true,
            data: avgMems,
            symbol: 'none',
            itemStyle: { color: '#10B981' },
            lineStyle: { width: 2 },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(16, 185, 129, 0.2)' },
                { offset: 1, color: 'rgba(16, 185, 129, 0.02)' }
              ])
            }
          },
          {
            name: 'Latency',
            type: 'line',
            smooth: true,
            yAxisIndex: 1,
            data: avgLats,
            symbol: 'none',
            itemStyle: { color: '#8B5CF6' },
            lineStyle: { width: 2, type: 'dashed' }
          }
        ]
      });
    }

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

    // Supabase Realtime subscription for instant updates
    function initRealtimeSubscription() {
      if (!supabaseClient) {
        console.log('Supabase client not available, using polling only');
        return;
      }

      try {
        const channel = supabaseClient.channel('modo-telemetry');

        const allowedStatuses = new Set(['ONLINE', 'OFFLINE', 'TIMEOUT', 'ERROR', 'UNKNOWN']);
        channel.on('broadcast', { event: 'telemetry' }, (payload) => {
          const data = payload && typeof payload === 'object' ? payload.payload : null;
          if (!data || !Array.isArray(data.nodes)) return;

          // Validate and convert broadcast entries to API format before merging
          const nodes = [];
          for (const entry of data.nodes) {
            if (!entry || typeof entry !== 'object') continue;
            if (typeof entry.node !== 'string') continue;
            const nodeName = entry.node.trim();
            if (!nodeName || nodeName.length > 64) continue;
            const rtt = safeMetricNumber(entry.rtt, 0);
            const boundedRtt = Math.max(0, Math.min(60000, Math.round(rtt)));
            const status = typeof entry.status === 'string' && allowedStatuses.has(entry.status)
              ? entry.status
              : 'UNKNOWN';
            nodes.push({
              node_name: nodeName,
              rtt_ms: boundedRtt,
              latency_ms: boundedRtt,
              scrape_duration_ms: boundedRtt,
              cpu_usage_percent: safePercent(entry.cpu),
              mem_usage_percent: safePercent(entry.mem),
              disk_usage_percent: safePercent(entry.disk),
              status,
            });
          }
          if (nodes.length === 0) return;

          // Merge with cached data (keep fields not in broadcast)
          const mergedNodes = nodes.map(newNode => {
            const cached = cachedNodesData.find(c => c.node_name === newNode.node_name) || {};
            return { ...cached, ...newNode };
          });

          cachedNodesData = mergedNodes;

          // Update UI components
          try { renderKPIs(mergedNodes); } catch(e) { console.debug('renderKPIs:', e); }
          try { renderTable(mergedNodes); } catch(e) { console.debug('renderTable:', e); }
          try { renderResourceChart(mergedNodes); } catch(e) { console.debug('renderResourceChart:', e); }
          try { renderLatencyChart(mergedNodes); } catch(e) { console.debug('renderLatencyChart:', e); }

          // Reset countdown to show fresh data indicator
          countdown = 15;
          const timer = document.getElementById('sync-timer');
          if (timer) timer.innerText = '实时';

          // Flash effect to indicate live update
          const badge = document.getElementById('live-clock-badge');
          if (badge) {
            badge.style.transition = 'color 0.2s';
            badge.style.color = '#22c55e';
            setTimeout(() => { badge.style.color = ''; }, 500);
          }
        });

        channel.subscribe((status) => {
          console.log('Realtime subscription status:', status);
          if (status === 'SUBSCRIBED') {
            console.log('✓ Supabase Realtime connected');
          }
        });

      } catch (e) {
        console.warn('Realtime subscription failed:', e);
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
        if (timer) timer.innerText = `${countdown}s`;
        updateClock();
      }, 1000);
    }

    // Init lifecycle
    window.addEventListener('DOMContentLoaded', () => {
      document.querySelectorAll('[data-curtain]').forEach((el) => {
        el.addEventListener('click', () => handleCurtainClick(el.getAttribute('data-curtain')));
      });
      document.getElementById('refresh-btn')?.addEventListener('click', () => fetchData());
      document.getElementById('login-btn')?.addEventListener('click', () => toggleAuthModal());
      document.getElementById('auth-modal-close')?.addEventListener('click', () => toggleAuthModal());
      document.getElementById('logout-btn')?.addEventListener('click', () => handleLogout());
      document.getElementById('auth-form')?.addEventListener('submit', handleAuth);

      updateClock();
      initCharts();
      fetchData();
      checkUserSession();
      startTimer();
      initRealtimeSubscription();  // Enable Supabase Realtime for instant updates
    });

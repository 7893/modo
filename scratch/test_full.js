const fs = require('fs');
const jsdom = require('jsdom');
const { JSDOM } = jsdom;

const html = fs.readFileSync('/home/ubuntu/nexus/scratch/live.html', 'utf-8');
const dom = new JSDOM(html, { runScripts: 'dangerously', beforeParse(window) {
  window.fetch = async (url) => {
    console.log('Mock fetch called for', url);
    if (url.includes('/api/nodes/latest')) {
      return {
        json: async () => ({ status: 'success', data: [{ node_name: 'test', scrape_duration_ms: 10, status: 'ONLINE' }] })
      };
    }
    if (url.includes('/api/ai/diagnostics')) {
      return {
        json: async () => ({ diagnostics: ['Test diag'] })
      };
    }
    return { json: async () => ({}) };
  };
  window.echarts = {
    init: () => ({
      setOption: (opt) => { console.log('setOption called for chart'); },
      resize: () => {}
    }),
    graphic: { LinearGradient: class {} }
  };
  window.tailwind = { config: {} };
} });

setTimeout(() => {
  console.log('Test completed.');
  process.exit(0);
}, 2000);

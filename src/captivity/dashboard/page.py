"""
Embedded HTML dashboard page.

Single-page application served at http://localhost:8787.
Uses vanilla HTML/CSS/JS with auto-refresh via fetch API.

No external dependencies — everything is embedded in this
Python string constant.
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Captivity Dashboard</title>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --border: #2a2d3a;
    --text: #e1e4ed;
    --muted: #8b8fa3;
    --accent: #6c5ce7;
    --green: #00b894;
    --red: #e17055;
    --orange: #fdcb6e;
    --blue: #74b9ff;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 24px;
  }
  .header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }
  .header h1 {
    font-size: 1.5rem;
    font-weight: 600;
    background: linear-gradient(135deg, var(--accent), var(--blue));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .header .badge {
    font-size: 0.75rem;
    padding: 2px 8px;
    border-radius: 12px;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--muted);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    transition: border-color 0.2s;
  }
  .card:hover { border-color: var(--accent); }
  .card h3 {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    margin-bottom: 8px;
  }
  .card .value {
    font-size: 1.8rem;
    font-weight: 700;
  }
  .card .sub {
    font-size: 0.85rem;
    color: var(--muted);
    margin-top: 4px;
  }
  .status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
  }
  .status-connected { background: var(--green); box-shadow: 0 0 8px var(--green); }
  .status-idle { background: var(--orange); }
  .status-error { background: var(--red); }
  .table-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
  }
  .table-card h3 {
    font-size: 0.9rem;
    margin-bottom: 12px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  table {
    width: 100%;
    border-collapse: collapse;
  }
  th {
    text-align: left;
    font-size: 0.75rem;
    color: var(--muted);
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  td {
    padding: 8px 12px;
    font-size: 0.85rem;
    border-bottom: 1px solid var(--border);
  }
  tr:last-child td { border-bottom: none; }
  .event-type {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
  }
  .event-login_success { background: rgba(0,184,148,0.15); color: var(--green); }
  .event-login_failure { background: rgba(225,112,85,0.15); color: var(--red); }
  .event-reconnect { background: rgba(253,203,110,0.15); color: var(--orange); }
  .event-session_end { background: rgba(116,185,255,0.15); color: var(--blue); }
  .footer {
    text-align: center;
    color: var(--muted);
    font-size: 0.75rem;
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
  }
  .empty { color: var(--muted); font-style: italic; font-size: 0.85rem; }
</style>
</head>
<body>
<div class="header">
  <h1>Captivity</h1>
  <span class="badge">Dashboard</span>
  <span class="badge" id="refresh-badge">auto-refresh: 5s</span>
</div>

<div class="grid">
  <div class="card">
    <h3>Connection</h3>
    <div class="value" id="conn-state">
      <span class="status-dot status-idle"></span>Loading...
    </div>
    <div class="sub" id="conn-network"></div>
  </div>
  <div class="card">
    <h3>Session Uptime</h3>
    <div class="value" id="uptime">—</div>
    <div class="sub" id="uptime-sub"></div>
  </div>
  <div class="card">
    <h3>Total Logins</h3>
    <div class="value" id="total-logins">—</div>
    <div class="sub" id="total-uptime-sub"></div>
  </div>
  <div class="card">
    <h3>Bandwidth</h3>
    <div class="value" id="bandwidth">—</div>
    <div class="sub" id="bandwidth-sub"></div>
  </div>
</div>

<div class="table-card">
  <h3>Network Statistics</h3>
  <table>
    <thead>
      <tr>
        <th>Network</th>
        <th>Logins</th>
        <th>Success</th>
        <th>Uptime</th>
        <th>Reconnects</th>
      </tr>
    </thead>
    <tbody id="networks-body">
      <tr><td colspan="5" class="empty">No data yet</td></tr>
    </tbody>
  </table>
</div>

<div class="table-card">
  <h3>Recent Events</h3>
  <table>
    <thead>
      <tr>
        <th>Time</th>
        <th>Event</th>
        <th>Network</th>
        <th>Details</th>
      </tr>
    </thead>
    <tbody id="events-body">
      <tr><td colspan="4" class="empty">No events yet</td></tr>
    </tbody>
  </table>
</div>

<div class="footer">
  Captivity — Autonomous captive portal login client
</div>

<script>
function formatBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  if (b < 1073741824) return (b/1048576).toFixed(1) + ' MB';
  return (b/1073741824).toFixed(1) + ' GB';
}
function formatHours(s) {
  return (s / 3600).toFixed(1) + 'h';
}

async function fetchJSON(url) {
  try {
    const r = await fetch(url);
    return await r.json();
  } catch(e) { return null; }
}

async function refresh() {
  const [status, stats, history] = await Promise.all([
    fetchJSON('/api/status'),
    fetchJSON('/api/stats'),
    fetchJSON('/api/history'),
  ]);

  if (status) {
    const dot = status.state === 'connected' ? 'status-connected'
              : status.state === 'error' ? 'status-error' : 'status-idle';
    document.getElementById('conn-state').innerHTML =
      '<span class="status-dot ' + dot + '"></span>' +
      status.state.charAt(0).toUpperCase() + status.state.slice(1);
    document.getElementById('conn-network').textContent =
      status.network ? 'Network: ' + status.network : '';
    document.getElementById('uptime').textContent = status.uptime_str || '—';
  }

  if (stats) {
    document.getElementById('total-logins').textContent = stats.total_logins || 0;
    document.getElementById('total-uptime-sub').textContent =
      'Total uptime: ' + formatHours(stats.total_uptime || 0);
    document.getElementById('bandwidth').textContent =
      formatBytes(stats.total_bandwidth || 0);

    const tbody = document.getElementById('networks-body');
    if (stats.networks && stats.networks.length > 0) {
      tbody.innerHTML = stats.networks.map(n =>
        '<tr><td>' + n.ssid + '</td><td>' + n.login_successes + '</td>' +
        '<td>' + n.success_rate + '%</td><td>' + formatHours(n.total_uptime) +
        '</td><td>' + n.reconnect_count + '</td></tr>'
      ).join('');
    }
  }

  if (history && history.length > 0) {
    const tbody = document.getElementById('events-body');
    tbody.innerHTML = history.map(e =>
      '<tr><td>' + e.time_str + '</td>' +
      '<td><span class="event-type event-' + e.event_type + '">' +
      e.event_type.replace('_', ' ') + '</span></td>' +
      '<td>' + e.network + '</td><td>' + (e.details || '') + '</td></tr>'
    ).join('');
  }
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>"""

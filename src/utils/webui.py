from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import json
import os
import socket
import utils.config as config
import utils.status as status
import re

LOG_FILE = "evictarr.log"


class LogHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.html_page().encode("utf-8"))

        elif self.path == "/health":
            result = status.health()
            self.send_response(200 if result["healthy"] else 503)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))

        elif self.path == "/logs":
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r") as f:
                    formatted_logs = []
                    log_pattern = re.compile(
                        r"^(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(?P<level>[A-Z]+)\] (?P<message>.*)$"
                    )

                    logs = f.readlines()[-config.log_lines :]

                    for log in logs:
                        match = log_pattern.match(log.strip())

                        if match:
                            time = (
                                f"<span class='log-time'>{match.group('time')}</span>"
                            )
                            level = f"<span class='log-level log-{match.group('level').lower()}'>{match.group('level')}</span>"
                            message = f"<span class='log-message'>{html.escape(match.group('message'))}</span>"
                            formatted_logs.append(
                                f"<div class='log-line'>{time} {level} {message}</div>"
                            )

                        else:  # fallback for unmatched lines
                            formatted_logs.append(
                                f"<div class='log-line'>{html.escape(log.strip())}</div>"
                            )

                    log_data = "\n".join(formatted_logs)
            else:
                log_data = "Log file not found."

            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(log_data.encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def html_page(self):
        hostname = socket.gethostname()
        return f"""
<html>
<head>
  <title>Evictarr Logs</title>
  <style>
    body {{
      background: #1e1e2f;
      color: #d0d0f0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, monospace;
      margin: 2rem;
    }}
    h1 {{
      color: #89b4fa;
      font-weight: 700;
      margin-bottom: 1rem;
      border-bottom: 2px solid #89b4fa;
      padding-bottom: 0.25rem;
      user-select: none;
    }}
    .log-container {{
      background: #2e2e4d;
      padding: 1rem;
      border-radius: 6px;
      overflow-y: auto;
      height: 80vh;
      box-shadow: 0 0 10px #0005;
      font-size: 0.9rem;
      font-family: monospace;
    }}
    .log-line {{ margin-bottom: 4px; }}
    .log-time {{ color: #aaa; }}
    .log-level {{ font-weight: bold; margin: 0 0.5rem; }}
    .log-info {{ color: #8ec07c; }}
    .log-error {{ color: #fb4934; }}
    .log-action {{ color: #e4fb34; }}
    .log-warning {{ color: #fabd2f; }}
    .log-debug {{ color: #83a598; }}
    .log-startup {{ color: #d3869b; }}
    .log-message {{ color: #ebdbb2; }}
    .status {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
      background: #2e2e4d;
      padding: 0.6rem 1rem;
      border-radius: 6px;
      margin-bottom: 1rem;
    }}
    .status-dot {{ width: 12px; height: 12px; border-radius: 50%; background: #888; flex: none; }}
    .status.healthy .status-dot {{ background: #8ec07c; }}
    .status.unhealthy .status-dot {{ background: #fb4934; }}
    .status-checks {{ color: #aaa; font-size: 0.85rem; }}
  </style>
  <script>
    function fetchLogs() {{
      fetch('/logs')
        .then(response => response.text())
        .then(data => {{
          const logContainer = document.getElementById('log');
          logContainer.innerHTML = data;
          logContainer.scrollTop = logContainer.scrollHeight;
        }});
    }}

    function fetchHealth() {{
      fetch('/health')
        .then(response => response.json())
        .then(h => {{
          const bar = document.getElementById('status');
          bar.className = 'status ' + (h.healthy ? 'healthy' : 'unhealthy');
          const client = h.client ? h.client.name + ' ' + h.client.version : '';
          document.getElementById('status-text').textContent =
            (h.healthy ? 'Healthy' : 'Unhealthy: ' + h.problems.join(', ')) +
            (client ? ' | ' + client : '');
          document.getElementById('status-checks').textContent =
            Object.entries(h.checks).map(([name, c]) => {{
              const ago = c.last_run ? Math.round(Date.now() / 1000 - c.last_run) + 's ago' : 'not run yet';
              return name + ' (' + ago + '): ' + c.summary;
            }}).join('  ·  ');
        }})
        .catch(() => {{
          document.getElementById('status').className = 'status unhealthy';
          document.getElementById('status-text').textContent = 'Evictarr is not responding';
        }});
    }}

    function refresh() {{ fetchLogs(); fetchHealth(); }}
    setInterval(refresh, {config.log_refresh_interval}000);
    window.onload = refresh;
  </script>
</head>
<body>
  <h1>Evictarr Logs ({hostname})</h1>
  <div id="status" class="status">
    <span class="status-dot"></span>
    <div>
      <div id="status-text">Checking status...</div>
      <div id="status-checks" class="status-checks"></div>
    </div>
  </div>
  <div id="log" class="log-container">Loading...</div>
</body>
</html>
"""

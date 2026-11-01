async function getJSON(url, opts) {
  const res = await fetch(url, opts);
  return res.json();
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

async function refreshHotspot() {
  const el = document.getElementById("hotspot-status");
  try {
    const s = await getJSON("/api/status");
    let html = "";
    if (s.mode === "ap") {
      html += `<div class="status-line">Mode: <span class="ok">Access Point</span></div>`;
      html += `<div class="status-line">SSID: ${escapeHtml(s.ap_ssid)}</div>`;
      html += `<div class="status-line">AP IP: ${escapeHtml(s.ip || "-")}</div>`;
      const clients = s.clients || [];
      html += `<div class="status-line">Connected clients: ${clients.length}</div>`;
      if (clients.length) {
        html += "<table><tr><th>MAC</th><th>IP</th><th>Host</th><th>Signal</th></tr>";
        for (const c of clients) {
          html += `<tr><td>${escapeHtml(c.mac)}</td><td>${escapeHtml(c.ip || "-")}</td>` +
                  `<td>${escapeHtml(c.hostname || "-")}</td><td>${escapeHtml(c.signal_dbm ?? "-")} dBm</td></tr>`;
        }
        html += "</table>";
      }
    } else {
      html += `<div class="status-line">Mode: <span class="ok">Wifi Client</span></div>`;
      html += `<div class="status-line">IP: ${escapeHtml(s.ip || "-")}</div>`;
      if (s.client) {
        html += `<div class="status-line">SSID: ${escapeHtml(s.client.ssid || "-")}</div>`;
        html += `<div class="status-line">Signal: ${escapeHtml(s.client.signal_dbm ?? "-")} dBm</div>`;
      }
    }
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = `<span class="err">Failed to load status</span>`;
  }
}

async function refreshSdr() {
  const el = document.getElementById("sdr-status");
  try {
    const s = await getJSON("/api/sdr/status");
    if (!s.connected) {
      el.innerHTML = `<span class="err">Not connected: ${escapeHtml(s.error || "unknown error")}</span>`;
      return;
    }
    el.innerHTML =
      `<div class="status-line">URI: ${escapeHtml(s.uri)}</div>` +
      `<div class="status-line">RX LO: ${(s.rx_lo_hz / 1e6).toFixed(3)} MHz</div>` +
      `<div class="status-line">TX LO: ${(s.tx_lo_hz / 1e6).toFixed(3)} MHz</div>` +
      `<div class="status-line">Sample rate: ${(s.sample_rate_hz / 1e6).toFixed(3)} MHz</div>` +
      `<div class="status-line">RX gain: ${s.rx_gain_db} dB (${escapeHtml(s.gain_control_mode)})</div>`;
  } catch (e) {
    el.innerHTML = `<span class="err">Failed to load SDR status</span>`;
  }
}

function drawSpectrum(magnitudes) {
  const canvas = document.getElementById("spectrum");
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  if (!magnitudes || !magnitudes.length) return;
  const min = Math.min(...magnitudes);
  const max = Math.max(...magnitudes);
  const range = Math.max(max - min, 1);
  ctx.strokeStyle = "#4caf50";
  ctx.beginPath();
  magnitudes.forEach((v, i) => {
    const x = (i / (magnitudes.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();
}

async function refreshSpectrum() {
  try {
    const s = await getJSON("/api/sdr/spectrum");
    if (s.ok) drawSpectrum(s.magnitude_db);
  } catch (e) {
    // SDR may be offline; ignore, status panel reports errors already
  }
}

document.getElementById("btn-rescan").addEventListener("click", async () => {
  await getJSON("/api/hotspot/rescan", { method: "POST" });
  setTimeout(refreshHotspot, 2000);
});

document.getElementById("btn-restart-ap").addEventListener("click", async () => {
  await getJSON("/api/hotspot/restart_ap", { method: "POST" });
  setTimeout(refreshHotspot, 2000);
});

document.getElementById("sdr-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {};
  const freq = document.getElementById("rx-freq").value;
  const gain = document.getElementById("rx-gain").value;
  const rate = document.getElementById("sample-rate").value;
  if (freq) payload.rx_lo_hz = Math.round(parseFloat(freq) * 1e6);
  if (gain) payload.rx_gain_db = parseFloat(gain);
  if (rate) payload.sample_rate_hz = Math.round(parseFloat(rate) * 1e6);
  await getJSON("/api/sdr/configure", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  refreshSdr();
});

document.getElementById("settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const uri = document.getElementById("pluto-uri").value;
  if (!uri) return;
  await getJSON("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pluto_uri: uri }),
  });
  refreshSdr();
});

async function loadSettings() {
  try {
    const s = await getJSON("/api/settings");
    document.getElementById("pluto-uri").value = s.pluto_uri || "";
  } catch (e) {
    // ignore
  }
}

loadSettings();
refreshHotspot();
refreshSdr();
setInterval(refreshHotspot, 5000);
setInterval(refreshSdr, 5000);
setInterval(refreshSpectrum, 3000);

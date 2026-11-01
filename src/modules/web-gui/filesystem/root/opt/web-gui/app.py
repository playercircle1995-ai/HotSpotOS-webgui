#!/usr/bin/env python3
"""HotSpotOS web dashboard.

Serves a single page showing:
  * auto-hotspot status (AP vs wifi-client mode, SSID, connected clients)
  * ADI Pluto+ SDR status and basic controls (frequency, gain, spectrum)

Runs as root (see web-gui.service) because reading hostapd/iw/dnsmasq state
and restarting networking services needs elevated privileges. There is no
authentication - this is intended to be reachable only over the hotspot's
own subnet. Do not expose this port to an untrusted network.
"""
import json
import os
import re
import subprocess
import threading
import time

from flask import Flask, jsonify, request, render_template

CONFIG_PATH = "/etc/web-gui/config.json"
DNSMASQ_LEASES = "/var/lib/misc/dnsmasq.leases"
WLAN_IFACE = "wlan0"

app = Flask(__name__)

_config_lock = threading.Lock()


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"port": 80, "pluto_uri": "ip:192.168.2.1"}


def save_config(cfg):
    with _config_lock:
        tmp_path = CONFIG_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
        os.replace(tmp_path, CONFIG_PATH)


def run(cmd, timeout=5):
    """Run a command, returning (ok, stdout). Never raises."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.returncode == 0, result.stdout
    except (OSError, subprocess.SubprocessError):
        return False, ""


def is_active(service):
    ok, out = run(["systemctl", "is-active", service])
    return out.strip() == "active"


def get_iface_ipv4(iface):
    ok, out = run(["ip", "-4", "-o", "addr", "show", iface])
    if not ok:
        return None
    match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
    return match.group(1) if match else None


def get_dnsmasq_leases():
    leases = []
    try:
        with open(DNSMASQ_LEASES, "r", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 4:
                    expiry, mac, ip, hostname = parts[0], parts[1], parts[2], parts[3]
                    leases.append(
                        {
                            "mac": mac,
                            "ip": ip,
                            "hostname": None if hostname == "*" else hostname,
                        }
                    )
    except OSError:
        pass
    return leases


def get_ap_stations():
    ok, out = run(["iw", "dev", WLAN_IFACE, "station", "dump"])
    stations = []
    if not ok:
        return stations
    current = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Station"):
            if current:
                stations.append(current)
            current = {"mac": line.split()[1]}
        elif current is not None and "signal:" in line:
            m = re.search(r"signal:\s*(-?\d+)", line)
            if m:
                current["signal_dbm"] = int(m.group(1))
    if current:
        stations.append(current)

    leases_by_mac = {l["mac"].lower(): l for l in get_dnsmasq_leases()}
    for station in stations:
        lease = leases_by_mac.get(station["mac"].lower())
        if lease:
            station["ip"] = lease["ip"]
            station["hostname"] = lease["hostname"]
    return stations


def get_client_wifi_info():
    ok, out = run(["iw", "dev", WLAN_IFACE, "link"])
    if not ok or "Not connected" in out:
        return None
    ssid_match = re.search(r"SSID:\s*(.+)", out)
    signal_match = re.search(r"signal:\s*(-?\d+)", out)
    return {
        "ssid": ssid_match.group(1).strip() if ssid_match else None,
        "signal_dbm": int(signal_match.group(1)) if signal_match else None,
    }


def get_hotspot_status():
    ap_mode = is_active("hostapd")
    status = {
        "mode": "ap" if ap_mode else "client",
        "hostapd_active": ap_mode,
        "dnsmasq_active": is_active("dnsmasq"),
        "interface": WLAN_IFACE,
        "ip": get_iface_ipv4(WLAN_IFACE),
    }
    if ap_mode:
        status["ap_ssid"] = os.environ.get("AUTO_HOTSPOT_NAME", "hotspot")
        status["clients"] = get_ap_stations()
    else:
        status["client"] = get_client_wifi_info()
    return status


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify(get_hotspot_status())


@app.route("/api/hotspot/rescan", methods=["POST"])
def api_hotspot_rescan():
    # Nudges the auto-hotspot watchdog to re-evaluate wifi vs AP mode on its
    # next run, and asks wpa_supplicant to retry scanning right away.
    run(["wpa_cli", "-i", WLAN_IFACE, "reconfigure"])
    return jsonify({"ok": True})


@app.route("/api/hotspot/restart_ap", methods=["POST"])
def api_hotspot_restart_ap():
    run(["systemctl", "restart", "hostapd"])
    run(["systemctl", "restart", "dnsmasq"])
    return jsonify({"ok": True})


# --- ADI Pluto+ SDR -------------------------------------------------------

_pluto_lock = threading.Lock()
_pluto_cache = {"device": None, "uri": None, "error": None, "ts": 0}
_PLUTO_CACHE_TTL = 2.0


def get_pluto(force=False):
    cfg = load_config()
    uri = cfg.get("pluto_uri", "ip:192.168.2.1")
    with _pluto_lock:
        if (
            not force
            and _pluto_cache["device"] is not None
            and _pluto_cache["uri"] == uri
            and time.time() - _pluto_cache["ts"] < _PLUTO_CACHE_TTL
        ):
            return _pluto_cache["device"], None
        try:
            import adi  # pyadi-iio, imported lazily so the dashboard still
            # works (minus SDR features) if the SDR stack failed to install

            device = adi.Pluto(uri=uri)
            _pluto_cache.update(device=device, uri=uri, error=None, ts=time.time())
            return device, None
        except Exception as exc:  # pylint: disable=broad-except
            _pluto_cache.update(device=None, uri=uri, error=str(exc), ts=time.time())
            return None, str(exc)


@app.route("/api/sdr/status")
def api_sdr_status():
    device, error = get_pluto()
    if device is None:
        return jsonify({"connected": False, "error": error})
    try:
        return jsonify(
            {
                "connected": True,
                "uri": _pluto_cache["uri"],
                "rx_lo_hz": int(device.rx_lo),
                "tx_lo_hz": int(device.tx_lo),
                "sample_rate_hz": int(device.sample_rate),
                "rx_rf_bandwidth_hz": int(device.rx_rf_bandwidth),
                "rx_gain_db": float(device.rx_hardwaregain_chan0),
                "gain_control_mode": device.gain_control_mode_chan0,
            }
        )
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"connected": False, "error": str(exc)})


@app.route("/api/sdr/configure", methods=["POST"])
def api_sdr_configure():
    device, error = get_pluto()
    if device is None:
        return jsonify({"ok": False, "error": error}), 503

    data = request.get_json(silent=True) or {}
    try:
        if "rx_lo_hz" in data:
            device.rx_lo = int(data["rx_lo_hz"])
        if "tx_lo_hz" in data:
            device.tx_lo = int(data["tx_lo_hz"])
        if "rx_gain_db" in data:
            device.gain_control_mode_chan0 = "manual"
            device.rx_hardwaregain_chan0 = float(data["rx_gain_db"])
        if "sample_rate_hz" in data:
            device.sample_rate = int(data["sample_rate_hz"])
        return jsonify({"ok": True})
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/api/sdr/spectrum")
def api_sdr_spectrum():
    device, error = get_pluto()
    if device is None:
        return jsonify({"ok": False, "error": error}), 503
    try:
        import numpy as np

        buffer_size = 4096
        device.rx_buffer_size = buffer_size
        device.rx_enabled_channels = [0]
        samples = device.rx()
        window = np.hanning(len(samples))
        spectrum = np.fft.fftshift(np.fft.fft(samples * window))
        magnitude_db = 20 * np.log10(np.abs(spectrum) + 1e-9)

        # Downsample to a fixed number of points for a light-weight response.
        points = 256
        bins = np.array_split(magnitude_db, points)
        reduced = [float(b.mean()) for b in bins]

        return jsonify(
            {
                "ok": True,
                "center_hz": int(device.rx_lo),
                "sample_rate_hz": int(device.sample_rate),
                "magnitude_db": reduced,
            }
        )
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET":
        return jsonify(load_config())

    data = request.get_json(silent=True) or {}
    cfg = load_config()
    if "pluto_uri" in data:
        cfg["pluto_uri"] = str(data["pluto_uri"])
    save_config(cfg)
    get_pluto(force=True)  # reconnect with the new URI on next request
    return jsonify({"ok": True, "config": cfg})


if __name__ == "__main__":
    cfg = load_config()
    app.run(host="0.0.0.0", port=int(cfg.get("port", 80)))

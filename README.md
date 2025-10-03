Chute Monitor – README (Design + Ops)
Overview
Purpose: Monitor chute fullness using a TF‑Luna LiDAR and display state locally (web UI) and via a USB tower light.
States: Empty (green) or Full (red), with consecutive-full filtering to avoid false alarms.
Runs headless on a Raspberry Pi as a systemd service; optional local kiosk UI.
Hardware
Raspberry Pi (with network)
TF‑Luna/TFmini LiDAR on UART /dev/ttyAMA0
USB tower light (CH340 serial) on /dev/ttyUSB0
Optional: small HDMI/USB screen for kiosk mode
Software Components
chute_monitor.py
Reads TF‑Luna UART frames, validates checksum, converts to inches
Calibration: stores empty_distance and full_distance in chute_calibration.json
Status inference: compares live distance to calibration; requires consecutive “full” reads before declaring full
Monitoring loop: default 1.0s interval
Light control over serial: green=empty, red=full
Logs to chute_monitor.log
web_ui.py (Flask)
REST API: /api/status, /api/scan, /api/start, /api/stop, /api/calibrate/empty, /api/calibrate/full, /api/config, /api/clear-calibration
Starts monitoring automatically when app starts
templates/index.html
Dashboard: distance (inches), status, confidence, config (scan interval, thresholds), calibration controls
Data Flow
LiDAR → UART frames → parse/validate → distance (inches)
Calibration → store empty/full distances → JSON
Monitor loop → scan → determine status → update light → expose via API → UI refresh
Calibration (Empty/Full)
Empty: Clear the chute; run “Calibrate Empty” (takes ~5 samples and averages)
Full: Place material to the desired full point; run “Calibrate Full” (also ~5 samples)
Distances stored in inches; shown in UI; can “Clear Calibration” any time
Status Logic (Simplified)
If distance ≤ full_distance → full
If distance ≥ empty_distance → empty
Else: compute fill ratio; enforce consecutive “full” readings to confirm full
Headless Operation
Systemd service: chute-monitor.service
Auto-starts on boot; logs available via:
systemctl status chute-monitor
journalctl -u chute-monitor -n 50 --no-pager
Web UI
URL: http://<pi-ip>:5000 (e.g., http://192.168.0.104:5000)
Controls: Single Scan, Calibrate Empty, Calibrate Full, Clear Calibration, Start/Stop Monitoring, Save Config
Shows: status, distance (inches), confidence, consecutive full count, calibration values
Kiosk Mode (Optional)
Auto-launch Chromium to the UI:
Install: sudo apt update && sudo apt install -y chromium-browser unclutter
Autostart file ~/.config/lxsession/LXDE-pi/autostart:
Reboot: sudo reboot
Light Behavior
On service start: sends “all off” to clear stale state
Empty → green on
Full (or needs attention) → red on
Configuration
Defaults: scan interval 1.0s, inference threshold 3 (consecutive fulls), full threshold 80%
Change in UI; persists in memory for the session
Calibration stored in chute_calibration.json (created on first save)
File Structure
chute_monitor.py – core logic, LiDAR + light control, monitoring loop
web_ui.py – Flask app + API, starts monitoring
templates/index.html – web dashboard
requirements.txt – Flask, pyserial, numpy
install_pi.sh – setup and systemd install (if present)
chute_calibration.json – created after calibration
Install/Deploy (Summary)
On Pi:
Create venv and install deps:
Ensure UART enabled and TF‑Luna on /dev/ttyAMA0; USB light on /dev/ttyUSB0
Start/enable service:
On Windows (update files to Pi):
Operations
Start/Stop: sudo systemctl start|stop chute-monitor
Logs: journalctl -u chute-monitor -n 50 --no-pager
Manual light off (if stuck after reboot):
Troubleshooting
No sensor reading: check /dev/ttyAMA0, UART enabled in raspi-config, wiring, power, service logs
USB light not responding: verify /dev/ttyUSB0 exists, not in use; test with manual serial commands above
UI not loading: service running, port 5000 open, use http://<pi-ip>:5000
“Unknown” status: calibrate both empty and full; ensure distinct distances
This design keeps the system simple, robust, and easy to maintain: measure → decide → show → light.

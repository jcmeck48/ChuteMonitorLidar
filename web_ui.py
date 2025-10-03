#!/usr/bin/env python3
"""
Web UI for Chute Monitor
"""

from flask import Flask, render_template, jsonify, request
from chute_monitor import get_monitor
from datetime import datetime

app = Flask(__name__)
monitor = get_monitor()
monitor.start_monitoring()  # Start monitoring immediately

@app.get("/")
def index():
	return render_template("index.html")

@app.get("/api/status")
def api_status():
	return jsonify(monitor.get_status_json())

@app.post("/api/calibrate/empty")
def api_calibrate_empty():
	result = monitor.calibrate_empty()
	return jsonify({"success": result})

@app.post("/api/calibrate/full")
def api_calibrate_full():
	result = monitor.calibrate_full()
	return jsonify({"success": result})

@app.post("/api/start")
def api_start():
	monitor.start_monitoring()
	return jsonify({"success": True, "running": monitor.running})

@app.post("/api/stop")
def api_stop():
	monitor.stop_monitoring()
	return jsonify({"success": True, "running": monitor.running})

@app.get("/api/scan")
def api_scan():
	# Force a fresh scan and update status
	distance, confidence = monitor.scan_chute(force_scan=True)
	status = monitor.determine_chute_status(distance, confidence)
	monitor.status.raw_distance = distance
	monitor.status.confidence = confidence
	monitor.status.last_scan = datetime.now()
	monitor.status.status = status
	return jsonify(monitor.get_status_json())

@app.get("/api/config")
def api_config():
	m = monitor
	return jsonify({
		"scan_interval": m.config.scan_interval,
		"inference_threshold": m.config.inference_threshold,
		"full_threshold": m.config.full_threshold,
		"calibrated": m.calibration_data["calibrated"],
		"empty_distance": m.calibration_data["empty_distance"],
		"full_distance": m.calibration_data["full_distance"]
	})

@app.post("/api/config")
def api_update_config():
	d = request.get_json(force=True, silent=True) or {}
	if "scan_interval" in d: monitor.config.scan_interval = float(d["scan_interval"])
	if "inference_threshold" in d: monitor.config.inference_threshold = int(d["inference_threshold"])
	if "full_threshold" in d: monitor.config.full_threshold = float(d["full_threshold"])
	return jsonify({"success": True})

@app.post("/api/clear-calibration")
def api_clear_calibration():
	monitor.calibration_data = {
		"empty_distance": 0.0,
		"full_distance": 0.0,
		"chute_angle_range": [0, 30],
		"calibrated": False
	}
	import os
	if os.path.exists(monitor.config.calibration_file):
		os.remove(monitor.config.calibration_file)
	return jsonify({"success": True})

if __name__ == "__main__":
	monitor.start_monitoring()
	app.run(host="0.0.0.0", port=5000, debug=False)

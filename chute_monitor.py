#!/usr/bin/env python3
"""
Chute Monitor - Raspberry Pi LiDAR-based chute monitoring system
"""

import time
import json
import threading
import logging
from datetime import datetime
from typing import Dict, List, Tuple
import numpy as np
from dataclasses import dataclass
import os

try:
	import serial
	LIDAR_AVAILABLE = True
except ImportError:
	LIDAR_AVAILABLE = False
	print("Warning: pyserial not available. Running in simulation mode.")

try:
	import serial
	LIGHT_AVAILABLE = True
except ImportError:
	LIGHT_AVAILABLE = False
	print("Warning: pyserial not available. Light control disabled.")

@dataclass
class ChuteConfig:
	scan_interval: float = 1.0
	inference_threshold: int = 3
	full_threshold: float = 0.8
	calibration_file: str = "chute_calibration.json"
	log_file: str = "chute_monitor.log"

@dataclass
class ChuteStatus:
	status: str
	confidence: float
	last_scan: datetime
	consecutive_full_readings: int = 0
	raw_distance: float = 0.0

class ChuteMonitor:
	def __init__(self, config: ChuteConfig):
		self.config = config
		self.status = ChuteStatus("unknown", 0.0, datetime.now())
		self.calibration_data = self.load_calibration()
		self.lidar = None
		self.light = None
		self.running = False
		self.monitor_thread = None

		logging.basicConfig(
			level=logging.INFO,
			format='%(asctime)s - %(levelname)s - %(message)s',
			handlers=[logging.FileHandler(config.log_file), logging.StreamHandler()]
		)
		self.logger = logging.getLogger(__name__)

		self.init_lidar()
		self.init_light()

	def init_lidar(self):
		if not LIDAR_AVAILABLE:
			self.logger.warning("LiDAR not available - running in simulation mode")
			return
		try:
			import serial
			self.lidar = serial.Serial("/dev/ttyAMA0", 115200, timeout=1)
			self.logger.info("LiDAR initialized successfully on /dev/ttyAMA0")
		except Exception as e:
			self.logger.error(f"Failed to initialize LiDAR: {e}")
			self.lidar = None

	def init_light(self):
		if not LIGHT_AVAILABLE:
			self.logger.warning("Light not available - running without light control")
			return
		try:
			import serial
			# Connect to the Adafruit USB tower light on /dev/ttyUSB0
			try:
				self.light = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
				# Send cleanup commands to turn off all lights
				self.light.write(bytes([0x28]))  # BUZZER_OFF
				self.light.write(bytes([0x21]))  # RED_OFF
				self.light.write(bytes([0x22]))  # YELLOW_OFF
				self.light.write(bytes([0x24]))  # GREEN_OFF
				self.logger.info("USB tower light initialized successfully on /dev/ttyUSB0")
			except Exception as e:
				self.logger.warning(f"USB tower light not found on /dev/ttyUSB0: {e}")
				self.light = None
		except Exception as e:
			self.logger.error(f"Failed to initialize USB tower light: {e}")
			self.light = None

	def set_light_color(self, color: str):
		"""Set the USB tower light color based on status"""
		if not self.light:
			return
		try:
			# Adafruit USB tower light commands
			if color == "red":
				# Turn off other lights first, then turn on red
				self.light.write(bytes([0x22]))  # YELLOW_OFF
				self.light.write(bytes([0x24]))  # GREEN_OFF
				self.light.write(bytes([0x11]))  # RED_ON
			elif color == "green":
				# Turn off other lights first, then turn on green
				self.light.write(bytes([0x21]))  # RED_OFF
				self.light.write(bytes([0x22]))  # YELLOW_OFF
				self.light.write(bytes([0x14]))  # GREEN_ON
			elif color == "yellow":
				# Turn off other lights first, then turn on yellow
				self.light.write(bytes([0x21]))  # RED_OFF
				self.light.write(bytes([0x24]))  # GREEN_OFF
				self.light.write(bytes([0x12]))  # YELLOW_ON
			elif color == "blue":
				# Turn off other lights first, then turn on yellow (closest to blue)
				self.light.write(bytes([0x21]))  # RED_OFF
				self.light.write(bytes([0x24]))  # GREEN_OFF
				self.light.write(bytes([0x12]))  # YELLOW_ON
			elif color == "white":
				# Turn on all lights for white
				self.light.write(bytes([0x11]))  # RED_ON
				self.light.write(bytes([0x12]))  # YELLOW_ON
				self.light.write(bytes([0x14]))  # GREEN_ON
			else:
				# Turn off all lights
				self.light.write(bytes([0x21]))  # RED_OFF
				self.light.write(bytes([0x22]))  # YELLOW_OFF
				self.light.write(bytes([0x24]))  # GREEN_OFF
		except Exception as e:
			self.logger.error(f"Failed to set USB tower light color: {e}")

	def load_calibration(self) -> Dict:
		if os.path.exists(self.config.calibration_file):
			try:
				with open(self.config.calibration_file, 'r') as f:
					return json.load(f)
			except Exception as e:
				self.logger.error(f"Failed to load calibration: {e}")
		return {
			"empty_distance": 0.0,  # inches
			"full_distance": 0.0,   # inches
			"chute_angle_range": [0, 30],
			"calibrated": False
		}

	def save_calibration(self):
		try:
			with open(self.config.calibration_file, 'w') as f:
				json.dump(self.calibration_data, f, indent=2)
			self.logger.info("Calibration saved successfully")
		except Exception as e:
			self.logger.error(f"Failed to save calibration: {e}")

	def calibrate_empty(self) -> bool:
		if not self.lidar:
			self.logger.warning("LiDAR not available for calibration")
			return False
		try:
			distances = []
			for i in range(5):
				d, c = self.scan_chute(force_scan=True)
				if d > 0:
					distances.append(d)
				self.logger.info(f"Calibration scan {i+1}: {d:.2f} inches")
			if distances:
				self.calibration_data["empty_distance"] = float(np.mean(distances))
				self.logger.info(f"Empty calibration: {self.calibration_data['empty_distance']:.2f} inches")
				return True
			else:
				self.logger.error("No valid distance readings for empty calibration")
		except Exception as e:
			self.logger.error(f"Calibration failed: {e}")
		return False

	def calibrate_full(self) -> bool:
		if not self.lidar:
			self.logger.warning("LiDAR not available for calibration")
			return False
		try:
			distances = []
			for i in range(5):
				d, c = self.scan_chute(force_scan=True)
				if d > 0:
					distances.append(d)
				self.logger.info(f"Calibration scan {i+1}: {d:.2f} inches")
			if distances:
				self.calibration_data["full_distance"] = float(np.mean(distances))
				self.calibration_data["calibrated"] = True
				self.save_calibration()
				self.logger.info(f"Full calibration: {self.calibration_data['full_distance']:.2f} inches")
				return True
			else:
				self.logger.error("No valid distance readings for full calibration")
		except Exception as e:
			self.logger.error(f"Calibration failed: {e}")
		return False

	def filter_chute_measurements(self, scan_data: List) -> List[float]:
		chute_distances = []
		min_angle, max_angle = self.calibration_data["chute_angle_range"]
		for (_, angle, distance) in scan_data:
			angle = angle % 360
			if min_angle <= angle <= max_angle and distance > 0:
				chute_distances.append(distance)
		return chute_distances

	def simulate_scan(self) -> float:
		import random
		return random.uniform(180, 1000)

	def scan_chute(self, force_scan: bool = False) -> Tuple[float, float]:
		# Always allow scanning if force_scan is True, even if not calibrated
		if not force_scan and not self.calibration_data["calibrated"]:
			return 0.0, 0.0
		if not self.lidar:
			distance = self.simulate_scan()
			confidence = 0.8
			return distance, confidence
		try:
			# TF-Luna UART frame (9 bytes): 0x59 0x59 Dist_L Dist_H Strength_L Strength_H Temp_L Temp_H Checksum
			# Try multiple times to get a valid reading
			for attempt in range(5):  # Reduced attempts to avoid blocking
				try:
					# Clear any old data
					self.lidar.reset_input_buffer()
					
					# Look for the header bytes
					header_found = False
					for _ in range(10):  # Reduced header search attempts
						b1 = self.lidar.read(1)
						if b1 == b'\x59':
							b2 = self.lidar.read(1)
							if b2 == b'\x59':
								header_found = True
								break
					
					if not header_found:
						continue
					
					# Read the rest of the frame
					payload = self.lidar.read(7)
					if len(payload) != 7:
						continue
					
					frame = b'\x59\x59' + payload
					checksum_ok = (sum(frame[:8]) & 0xFF) == frame[8]
					if not checksum_ok:
						continue
					
					dist_cm = frame[2] | (frame[3] << 8)
					strength = frame[4] | (frame[5] << 8)
					
					# Convert cm to inches and compute confidence
					distance = float(dist_cm) * 10.0 / 25.4  # Convert mm to inches
					confidence = min(max(strength / 500.0, 0.0), 1.0)
					
					# Only return if we got a reasonable reading (in inches)
					if distance > 0 and distance < 2000:  # Reasonable range in inches
						return distance, confidence
				except Exception as e:
					# If we get a serial error, try again
					if "device disconnected" in str(e) or "multiple access" in str(e):
						continue
					else:
						raise e
			
			# If we couldn't get a valid reading after all attempts
			return 0.0, 0.0
		except Exception as e:
			self.logger.error(f"Scan failed: {e}")
			return 0.0, 0.0

	def determine_chute_status(self, distance: float, confidence: float) -> str:
		if not self.calibration_data["calibrated"]:
			return "unknown"
		if confidence < 0.1:  # Lower confidence threshold
			return "unknown"
		empty_d = self.calibration_data["empty_distance"]
		full_d = self.calibration_data["full_distance"]
		
		# Handle edge cases where distance is very close to calibration values
		if distance <= full_d:
			return "full"
		elif distance >= empty_d:
			return "empty"
		
		# Calculate fill percentage
		fill = 1.0 - ((distance - full_d) / (empty_d - full_d))
		fill = max(0.0, min(1.0, fill))
		
		if fill >= self.config.full_threshold:
			return "full"
		elif fill >= 0.3:
			return "not_full"
		else:
			return "empty"

	def update_status(self):
		d, c = self.scan_chute()
		ns = self.determine_chute_status(d, c)
		if ns == "full":
			self.status.consecutive_full_readings += 1
		else:
			self.status.consecutive_full_readings = 0
		if ns == "full" and self.status.consecutive_full_readings >= self.config.inference_threshold:
			fs = "needs_attention"
		else:
			fs = ns
		self.status.status = fs
		self.status.confidence = c
		self.status.last_scan = datetime.now()
		self.status.raw_distance = d
		
		# Set light color based on status - only 2 states
		if fs == "full" or fs == "needs_attention":
			self.set_light_color("red")  # Red = Full
		else:
			self.set_light_color("green")  # Green = Empty (or anything else)
		
		self.logger.info(f"Chute status: {fs} (distance: {d:.2f} inches, confidence: {c:.2f})")

	def start_monitoring(self):
		if self.running: return
		self.running = True
		self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
		self.monitor_thread.start()
		self.logger.info("Chute monitoring started")

	def stop_monitoring(self):
		self.running = False
		if self.monitor_thread:
			self.monitor_thread.join()
		self.logger.info("Chute monitoring stopped")

	def _monitor_loop(self):
		while self.running:
			try:
				self.update_status()
				time.sleep(self.config.scan_interval)
			except Exception as e:
				self.logger.error(f"Monitoring loop error: {e}")
				time.sleep(5)

	def get_status_json(self) -> Dict:
		return {
			"status": self.status.status,
			"confidence": self.status.confidence,
			"last_scan": self.status.last_scan.isoformat(),
			"consecutive_full_readings": self.status.consecutive_full_readings,
			"raw_distance": self.status.raw_distance,
			"calibrated": self.calibration_data["calibrated"],
			"running": self.running
		}

	def cleanup(self):
		self.stop_monitoring()
		if self.lidar:
			try:
				self.lidar.close()
			except Exception:
				pass
		if self.light:
			try:
				self.light.write(bytes([0x21]))  # RED_OFF
				self.light.write(bytes([0x22]))  # YELLOW_OFF
				self.light.write(bytes([0x24]))  # GREEN_OFF
				self.light.close()
			except Exception:
				pass

_monitor = None
def get_monitor() -> ChuteMonitor:
	global _monitor
	if _monitor is None:
		_monitor = ChuteMonitor(ChuteConfig())
	return _monitor

if __name__ == "__main__":
	import sys
	m = get_monitor()
	if len(sys.argv) > 1:
		cmd = sys.argv[1]
		if cmd == "calibrate-empty":
			print("Calibrating empty..."); print(m.calibrate_empty())
		elif cmd == "calibrate-full":
			print("Calibrating full..."); print(m.calibrate_full())
		elif cmd == "start":
			print("Starting chute monitoring...")
			m.start_monitoring()
			try:
				while True: time.sleep(1)
			except KeyboardInterrupt:
				print("\nStopping monitor..."); m.cleanup()
		elif cmd == "status":
			m.update_status(); print(json.dumps(m.get_status_json(), indent=2))
		else:
			print("Usage: python chute_monitor.py [calibrate-empty|calibrate-full|start|status]")
	else:
		print("Usage: python chute_monitor.py [calibrate-empty|calibrate-full|start|status]")


"""
FileStorageSensor test: verifies device emits storage-status system messages with size/percent fields.

Usage:
  python file_storage_sensor_test.py COM4 115200
"""

import json
import serial
import sys
import time
from datetime import datetime


def print_with_timestamp(message: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {message}")


class Client:
    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.ser: serial.Serial | None = None

    def connect(self) -> bool:
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print_with_timestamp(f"Connected to {self.port} @ {self.baudrate}")
            return True
        except Exception as e:
            print_with_timestamp(f"Connection error: {e}")
            return False

    def disconnect(self):
        if self.ser:
            self.ser.close()
            print_with_timestamp("Disconnected")

    def _read_available(self) -> str:
        if self.ser.in_waiting > 0:
            try:
                return self.ser.read(self.ser.in_waiting).decode('utf-8', errors='replace')
            except Exception:
                return ""
        return ""

    def read_until(self, timeout: float, predicate) -> dict | None:
        start = time.time()
        buffer = ""
        while time.time() - start < timeout:
            chunk = self._read_available()
            if chunk:
                buffer += chunk
                if "\n" in buffer:
                    parts = buffer.split("\n")
                    for line in parts[:-1]:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            print_with_timestamp(f"RECEIVED: {line}")
                            if predicate(obj):
                                return obj
                        except json.JSONDecodeError:
                            print_with_timestamp(f"Non-JSON response: {line}")
                    buffer = parts[-1]
            time.sleep(0.05)
        return None


def validate_storage_message(obj: dict) -> bool:
    if obj.get("message_source") != "file_storage_sensor":
        return False
    m = obj.get("message")
    if not isinstance(m, dict):
        return False
    required = ["event", "path", "total_bytes", "free_bytes", "used_bytes", "free_percent"]
    if any(k not in m for k in required):
        return False
    if m.get("event") != "storage-status":
        return False
    # Basic value checks
    if not isinstance(m.get("total_bytes"), int):
        return False
    if not isinstance(m.get("free_bytes"), int):
        return False
    if not isinstance(m.get("used_bytes"), int):
        return False
    if not isinstance(m.get("free_percent"), (int, float)):
        return False
    if m.get("total_bytes") < 0 or m.get("free_bytes") < 0 or m.get("used_bytes") < 0:
        return False
    if m.get("free_percent") < 0 or m.get("free_percent") > 100:
        return False
    return True


def run(port: str, baud: int) -> bool:
    c = Client(port, baud)
    if not c.connect():
        return False
    try:
        print_with_timestamp("Waiting for FileStorageSensor message...")
        msg = c.read_until(15.0, validate_storage_message)
        if not msg:
            print_with_timestamp("❌ No storage-status message received")
            return False
        print_with_timestamp("✅ storage-status message received and validated")
        return True
    finally:
        c.disconnect()


def main():
    port = 'COM4'
    baud = 115200
    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        baud = int(sys.argv[2])
    ok = run(port, baud)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())



"""
Send a sequence to AlphaCommsManager from a CSV file.

CSV format expected (as in nicegui/sequences/new-format-without-stop.csv):
  Row 1: header names
  Row 2: optional types (e.g., int,bool,double,...)
  Rows 3+: data rows

Flow:
  - Open serial
  - Send sequence init (number_of_states = number of data rows)
  - For each i: wait for sequence_request i, send JSON line with "sequence_cmd" and "state"
  - Wait for sequence_complete

Usage:
  python send_sequence_from_csv.py /path/to/sequence.csv COM4 115200
"""

import csv
import json
import serial
import sys
import time
from datetime import datetime


def print_with_timestamp(message: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {message}")


def coerce(value: str, typ: str | None):
    if typ is None:
        # Best-effort infer
        v = value.strip()
        if v in ("1", "0"):
            return v == "1"
        try:
            if "." in v:
                return float(v)
            return int(v)
        except Exception:
            return v
    t = typ.strip().lower()
    v = value.strip()
    try:
        if t in ("bool", "boolean"):
            return v in ("1", "true", "True")
        if t in ("int", "integer"):
            return int(float(v))
        if t in ("double", "float"):
            return float(v)
        return v
    except Exception:
        return v


def read_sequence_csv(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        all_rows = list(reader)
    if not all_rows:
        return rows
    headers = [h.strip() for h in all_rows[0]]
    types = None
    start_idx = 1
    if len(all_rows) > 1 and any(t in ("int", "bool", "double", "float") for t in all_rows[1]):
        types = [t.strip() for t in all_rows[1]]
        start_idx = 2
    for r in all_rows[start_idx:]:
        if not any(cell.strip() for cell in r):
            continue
        obj = {}
        for i, h in enumerate(headers):
            val = r[i] if i < len(r) else ""
            t = types[i] if (types and i < len(types)) else None
            obj[h] = coerce(val, t)
        rows.append(obj)
    return rows


class SequenceSender:
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

    def send_json(self, obj: dict) -> None:
        s = json.dumps(obj) + "\n"
        self.ser.write(s.encode())
        print_with_timestamp(f"SENT: {s.strip()}")

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

    def wait_for_command(self, name: str, timeout: float) -> dict | None:
        return self.read_until(timeout, lambda o: (
            o.get("command") == name) or (
            isinstance(o.get("message"), dict) and o.get("message", {}).get("command") == name)
        )

    def wait_for_state(self, state: str, timeout: float) -> bool:
        def pred(o):
            cmd = o.get("command")
            msg = o.get("message") if isinstance(o.get("message"), dict) else None
            if cmd == "state_notification":
                return o.get("state") == state
            if msg and msg.get("command") == "state_notification":
                return msg.get("state") == state
            return False
        return self.read_until(timeout, pred) is not None

    def wait_for_log_contains(self, needle: str, timeout: float) -> bool:
        def pred(obj):
            if obj.get("message_source") == "SysLogger":
                m = obj.get("message")
                return isinstance(m, str) and needle in m
            return False
        return self.read_until(timeout, pred) is not None

    def run(self, csv_path: str) -> bool:
        # Read CSV
        entries = read_sequence_csv(csv_path)
        if not entries:
            print_with_timestamp("❌ No rows found in CSV")
            return False
        print_with_timestamp(f"Loaded {len(entries)} rows from CSV")

        # Ensure device is idle before starting
        print_with_timestamp("Waiting for idle state...")
        if not self.wait_for_state("idle", 10.0):
            print_with_timestamp("❌ Device did not report idle state")
            return False
        print_with_timestamp("✅ Idle state confirmed")

        # Send init
        init = {
            "message_source": "proteus",
            "timestamp": datetime.now().isoformat(),
            "message": {
                "command": "sequence_cmd",
                "number_of_states": len(entries)
            }
        }
        self.send_json(init)
        if not self.wait_for_command("sequence_ack", 10.0):
            print_with_timestamp("❌ No sequence init ACK")
            return False
        print_with_timestamp("✅ Init ACK")

        # For each line: wait for request, send line, wait ack
        for i, row in enumerate(entries):
            print_with_timestamp(f"Waiting for sequence_request {i}...")
            req = self.wait_for_command("sequence_request", 20.0)
            if not req:
                print_with_timestamp(f"❌ No sequence_request for {i}")
                return False
            requested = req.get("sequence_request")
            if requested is None and isinstance(req.get("message"), dict):
                requested = req.get("message", {}).get("sequence_request")
            if requested != i:
                print_with_timestamp(f"❌ Expected request {i}, got {requested}")
                return False
            print_with_timestamp(f"✅ request {i}")

            # Build state dict from row (keys match controller expectations)
            state = {k: v for k, v in row.items() if k not in ("cmd",)}
            payload = {
                "message_source": "proteus",
                "timestamp": datetime.now().isoformat(),
                "message": {
                    "command": "sequence_cmd",
                    "sequence_number": i,
                    "state": state,
                }
            }
            self.send_json(payload)
            if not self.wait_for_command("sequence_ack", 10.0):
                print_with_timestamp(f"❌ No ACK for line {i}")
                return False
            print_with_timestamp(f"✅ ACK line {i}")

        # Expect completion
        if not self.wait_for_command("sequence_complete", 20.0):
            print_with_timestamp("❌ No sequence_complete")
            return False
        print_with_timestamp("✅ sequence_complete")

        # Post-send verification: ensure SequenceController is executing
        if not self.wait_for_log_contains("SequenceController: Received sequence completion event", 10.0):
            print_with_timestamp("❌ SequenceController did not receive completion event")
            return False
        print_with_timestamp("✅ SequenceController received completion event")

        for i in range(len(entries)):
            if not self.wait_for_log_contains(f"Executing sequence {i}", 15.0):
                print_with_timestamp(f"❌ Missing 'Executing sequence {i}' log")
                return False
            if not self.wait_for_log_contains(f"Dispatched sequence {i} commands", 15.0):
                print_with_timestamp(f"❌ Missing 'Dispatched sequence {i} commands' log")
                return False
            print_with_timestamp(f"✅ Executed line {i}")

        if not self.wait_for_log_contains("SequenceController: All sequences completed", 20.0):
            print_with_timestamp("❌ Missing final completion log from SequenceController")
            return False
        print_with_timestamp("✅ SequenceController completion verified")
        return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python send_sequence_from_csv.py /path/to/sequence.csv [COM_PORT] [BAUD]")
        return 2
    csv_path = sys.argv[1]
    port = sys.argv[2] if len(sys.argv) > 2 else 'COM4'
    baud = int(sys.argv[3]) if len(sys.argv) > 3 else 115200
    sender = SequenceSender(port, baud)
    if not sender.connect():
        return 1
    try:
        ok = sender.run(csv_path)
        return 0 if ok else 3
    finally:
        sender.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())



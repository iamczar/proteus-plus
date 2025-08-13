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
        # Backlog of already-read messages so we don't drop lines that
        # arrive in the same read chunk after a predicate match
        self._backlog: list[dict] = []

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
            # First, drain any backlog captured from a previous call
            if self._backlog:
                # Iterate over a snapshot so we can pop safely
                remaining: list[dict] = []
                matched: dict | None = None
                for obj in self._backlog:
                    if matched is None and predicate(obj):
                        matched = obj
                        continue
                    remaining.append(obj)
                self._backlog = remaining
                if matched is not None:
                    return matched

            chunk = self._read_available()
            if chunk:
                buffer += chunk
                if "\n" in buffer:
                    parts = buffer.split("\n")
                    # Parse all complete lines first so we can backlog
                    parsed_objs: list[dict] = []
                    for line in parts[:-1]:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            print_with_timestamp(f"RECEIVED: {line}")
                            parsed_objs.append(obj)
                        except json.JSONDecodeError:
                            print_with_timestamp(f"Non-JSON response: {line}")
                    # Scan for first match; backlog the rest in order
                    matched_idx = None
                    for idx, obj in enumerate(parsed_objs):
                        if predicate(obj):
                            matched_idx = idx
                            break
                    if matched_idx is not None:
                        # Backlog any remaining objects after the match
                        if matched_idx + 1 < len(parsed_objs):
                            self._backlog.extend(parsed_objs[matched_idx + 1:])
                        return parsed_objs[matched_idx]
                    # No match yet; stash nothing since we'll continue looping
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

    def wait_for_sc_event(self, event: str, sequence: int | None = None, timeout: float = 10.0, total_sequences: int | None = None) -> bool:
        def pred(obj):
            if obj.get("message_source") != "sequence_controller":
                return False
            m = obj.get("message")
            if not isinstance(m, dict):
                return False
            if m.get("event") != event:
                return False
            if sequence is not None and m.get("sequence") != sequence:
                return False
            if total_sequences is not None and m.get("total_sequences") != total_sequences:
                return False
            return True
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

        # Post-send verification using structured system messages from SequenceController
        total = len(entries)
        saw_exec0 = self.wait_for_sc_event("executing", sequence=0, timeout=15.0, total_sequences=total)
        if not saw_exec0:
            print_with_timestamp("❌ SequenceController did not start executing sequence 0")
            return False
        print_with_timestamp("✅ SequenceController started executing")

        # We already consumed executing(0); don't require it again in loop
        start_idx = 1 if saw_exec0 else 0
        for i in range(start_idx, total):
            if not self.wait_for_sc_event("executing", sequence=i, timeout=15.0, total_sequences=total):
                print_with_timestamp(f"❌ Missing executing event for sequence {i}")
                return False
            if not self.wait_for_sc_event("dispatched", sequence=i, timeout=15.0, total_sequences=total):
                print_with_timestamp(f"❌ Missing dispatched event for sequence {i}")
                return False
            print_with_timestamp(f"✅ Executed and dispatched line {i}")

        if not self.wait_for_sc_event("execution-complete", total_sequences=len(entries), timeout=20.0):
            print_with_timestamp("❌ Missing execution-complete event from SequenceController")
            return False
        print_with_timestamp("✅ SequenceController execution complete event verified")
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



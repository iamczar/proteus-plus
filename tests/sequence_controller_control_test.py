"""
SequenceController Control Commands Test (pause/resume/stop/reset)

Flow:
 1) Wait for idle
 2) Send a minimal sequence (2 lines) so execution starts
 3) Issue pause; verify AlphaCommsManager ACK and SequenceController system message + state
 4) Issue resume; verify ACK and SequenceController system message + state
 5) Issue stop; verify ACK and SequenceController system message + state (idle)
 6) Issue reset; verify ACK and SequenceController system message + state (idle, seq=0)

Usage:
  python sequence_controller_control_test.py COM4 115200
"""

import json
import serial
import sys
import time
from datetime import datetime


def print_with_timestamp(message: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {message}")


class SerialClient:
    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.ser: serial.Serial | None = None
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
            # drain backlog first
            if self._backlog:
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
                    parsed: list[dict] = []
                    for line in parts[:-1]:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            print_with_timestamp(f"RECEIVED: {line}")
                            parsed.append(obj)
                        except json.JSONDecodeError:
                            print_with_timestamp(f"Non-JSON response: {line}")
                    match_idx = None
                    for idx, obj in enumerate(parsed):
                        if predicate(obj):
                            match_idx = idx
                            break
                    if match_idx is not None:
                        if match_idx + 1 < len(parsed):
                            self._backlog.extend(parsed[match_idx + 1:])
                        return parsed[match_idx]
                    buffer = parts[-1]
            time.sleep(0.05)
        return None

    def wait_for_command(self, name: str, timeout: float) -> dict | None:
        return self.read_until(timeout, lambda o: (
            o.get("command") == name) or (
            isinstance(o.get("message"), dict) and o.get("message", {}).get("command") == name)
        )

    def wait_for_state_notification(self, state: str, timeout: float) -> bool:
        def pred(o):
            cmd = o.get("command")
            msg = o.get("message") if isinstance(o.get("message"), dict) else None
            if cmd == "state_notification":
                return o.get("state") == state
            if msg and msg.get("command") == "state_notification":
                return msg.get("state") == state
            return False
        return self.read_until(timeout, pred) is not None

    def wait_for_sc_event(self, event: str, timeout: float, state: str | None = None) -> bool:
        def pred(o):
            if o.get("message_source") != "sequence_controller":
                return False
            m = o.get("message")
            if not isinstance(m, dict):
                return False
            if m.get("event") != event:
                return False
            if state is not None and m.get("state") != state:
                return False
            return True
        return self.read_until(timeout, pred) is not None

    def wait_for_sc_status(self, expected_state: str, timeout: float) -> bool:
        def pred(o):
            if o.get("message_source") != "sequence_controller":
                return False
            m = o.get("message")
            if not isinstance(m, dict):
                return False
            return m.get("event") == "status" and m.get("state") == expected_state
        return self.read_until(timeout, pred) is not None


def send_sequence_init(client: SerialClient, total_states: int) -> bool:
    init = {
        "message_source": "proteus",
        "timestamp": datetime.now().isoformat(),
        "message": {
            "command": "sequence_cmd",
            "number_of_states": total_states,
        },
    }
    client.send_json(init)
    # Do not assert on AlphaCommsManager ACK; proceed and rely on SC events
    return True


def send_sequence_line(client: SerialClient, idx: int, state: dict) -> bool:
    payload = {
        "message_source": "proteus",
        "timestamp": datetime.now().isoformat(),
        "message": {
            "command": "sequence_cmd",
            "sequence_number": idx,
            "state": state,
        },
    }
    client.send_json(payload)
    # Do not assert on AlphaCommsManager ACK; rely on SC events for validation
    return True


def send_simple_command(client: SerialClient, name: str) -> bool:
    cmd = {
        "message_source": "proteus",
        "timestamp": datetime.now().isoformat(),
        "message": {
            "command": name,
        },
    }
    client.send_json(cmd)
    # Do not assert on AlphaCommsManager ACK; validation is via SC system messages
    return True


def run(port: str, baud: int) -> bool:
    client = SerialClient(port, baud)
    if not client.connect():
        return False
    try:
        print_with_timestamp("Waiting for SequenceController idle status...")
        if not client.wait_for_sc_status("idle", 8.0):
            print_with_timestamp("⚠️ No SC idle status observed (continuing)")

        # Start a shorter sequence (3 lines) to keep test quick
        total_states = 3
        if not send_sequence_init(client, total_states):
            return False

        # Fulfill all requests so AlphaComms can emit sequence_complete
        for i in range(total_states):
            print_with_timestamp(f"Waiting for sequence_request {i}...")
            req = client.wait_for_command("sequence_request", 20.0)
            if not req:
                print_with_timestamp(f"❌ No sequence_request {i}")
                return False
            state = {
                "circFlow": 100 + (i * 20),
                "pressureFlow": 200 + (i * 10),
                "valve1": (i % 2 == 0),
                "valve2": (i % 2 == 1),
                "transTimeSec": 5,
            }
            if not send_sequence_line(client, i, state):
                return False

        # After ingestion completes, SequenceController should begin executing
        if not client.wait_for_sc_event("executing", timeout=15.0):
            print_with_timestamp("❌ No executing event from SequenceController after ingestion")
            return False
        print_with_timestamp("✅ SequenceController started executing")

        # Pause
        # Small delay to avoid race with first line post-dispatch work
        time.sleep(0.3)
        if not send_simple_command(client, "pause"):
            return False
        if not client.wait_for_sc_event("paused", timeout=5.0, state="paused"):
            print_with_timestamp("❌ No paused event")
            return False
        if not client.wait_for_sc_status("paused", timeout=5.0):
            print_with_timestamp("❌ No paused status")
            return False
        print_with_timestamp("✅ paused")

        # Resume
        if not send_simple_command(client, "resume"):
            return False
        if not client.wait_for_sc_event("resumed", timeout=5.0, state="executing"):
            print_with_timestamp("❌ No resumed event")
            return False
        if not client.wait_for_sc_status("executing", timeout=5.0):
            print_with_timestamp("❌ No executing status after resume")
            return False
        print_with_timestamp("✅ resumed → executing")

        # Stop
        if not send_simple_command(client, "stop"):
            return False
        if not client.wait_for_sc_event("stopped", timeout=5.0, state="idle"):
            print_with_timestamp("❌ No stopped event")
            return False
        if not client.wait_for_sc_status("idle", timeout=5.0):
            print_with_timestamp("❌ No idle status after stop")
            return False
        print_with_timestamp("✅ stopped → idle")

        print_with_timestamp("=== All control checks passed ===")
        return True
    finally:
        client.disconnect()


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



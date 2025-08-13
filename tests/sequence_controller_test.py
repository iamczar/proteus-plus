"""
SequenceController Integration Test

This test exercises the full flow over serial:
1) Wait for device idle
2) Send sequence init and 3 lines (0-indexed)
3) Verify AlphaCommsManager sends sequence_complete
4) Verify SequenceController receives completion event and executes each line
5) Verify SequenceController reports all sequences completed

Usage:
  python sequence_controller_test.py COM4 115200
"""

import serial
import time
import json
from datetime import datetime

def print_with_timestamp(message: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {message}")

class SequenceControllerTester:
    def __init__(self, port='COM4', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    def connect(self) -> bool:
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print_with_timestamp(f"Connected to {self.port} at {self.baudrate} baudrate")
            return True
        except Exception as e:
            print_with_timestamp(f"Connection error: {e}")
            return False

    def disconnect(self):
        if self.ser:
            self.ser.close()
            print_with_timestamp("Disconnected")

    def send_json(self, obj: dict) -> bool:
        try:
            s = json.dumps(obj) + "\n"
            self.ser.write(s.encode())
            print_with_timestamp(f"SENT: {s.strip()}")
            return True
        except Exception as e:
            print_with_timestamp(f"Error sending command: {e}")
            return False

    def _read_available(self) -> str:
        if self.ser.in_waiting > 0:
            try:
                data = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='replace')
                return data
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
                    lines = buffer.split("\n")
                    for line in lines[:-1]:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            print_with_timestamp(f"RECEIVED: {line}")
                            if predicate(obj):
                                return obj
                        except json.JSONDecodeError:
                            # Not JSON: log line for visibility and allow string matching helpers to handle
                            print_with_timestamp(f"Non-JSON response: {line}")
                    buffer = lines[-1]
            time.sleep(0.05)
        return None

    def wait_for_state(self, state: str, timeout: float = 10.0) -> bool:
        def pred(obj):
            # Accept state_notification messages from either top-level command or nested message
            cmd = obj.get("command")
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else None
            if cmd == "state_notification":
                return obj.get("state") == state or obj.get("state") == state
            if msg and msg.get("command") == "state_notification":
                return msg.get("state") == state
            return False
        return self.read_until(timeout, pred) is not None

    def wait_for_command(self, command: str, timeout: float = 10.0) -> dict | None:
        return self.read_until(timeout, lambda o: (
            o.get("command") == command) or (
            isinstance(o.get("message"), dict) and o.get("message", {}).get("command") == command)
        )

    def wait_for_log_contains(self, needle: str, timeout: float = 10.0) -> bool:
        def pred(obj):
            # SysLogger messages carry a string under 'message'
            if obj.get("message_source") == "SysLogger":
                m = obj.get("message")
                if isinstance(m, str) and needle in m:
                    return True
            return False
        return self.read_until(timeout, pred) is not None

    def send_sequence_init(self, total_states: int = 3) -> bool:
        init = {
            "message_source": "proteus",
            "timestamp": datetime.now().isoformat(),
            "message": {
                "command": "sequence_cmd",
                "number_of_states": total_states
            }
        }
        if not self.send_json(init):
            return False
        ack = self.wait_for_command("sequence_ack", timeout=10.0)
        if not ack:
            print_with_timestamp("❌ No sequence init ACK")
            return False
        print_with_timestamp("✅ Sequence init ACK")
        return True

    def run(self) -> bool:
        print_with_timestamp("=== SequenceController Integration Test ===")

        # 1) Wait for idle (state_notification idle)
        print_with_timestamp("Waiting for idle state...")
        self.wait_for_state("idle", timeout=5.0)  # non-fatal

        # 2) Send sequence init
        if not self.send_sequence_init(3):
            return False

        # 3) For each i=0..2: wait for sequence_request i, send line i, wait for sequence_ack
        for i in range(3):
            print_with_timestamp(f"Waiting for sequence_request {i}...")
            req = self.wait_for_command("sequence_request", timeout=20.0)
            if not req:
                print_with_timestamp(f"❌ Did not receive sequence_request {i}")
                return False
            # Extract requested line safely
            requested_line = req.get("sequence_request")
            if requested_line is None and isinstance(req.get("message"), dict):
                requested_line = req.get("message", {}).get("sequence_request")
            if requested_line != i:
                print_with_timestamp(f"❌ Expected request {i}, got {requested_line}")
                return False
            print_with_timestamp(f"✅ Received sequence_request {i}")

            # Prepare a realistic line payload (0-indexed)
            line = {
                "message_source": "proteus",
                "timestamp": datetime.now().isoformat(),
                "message": {
                    "command": "sequence_cmd",
                    "sequence_number": i,
                    "state": {
                        "circFlow": 100 + (i * 50),
                        "pressureFlow": 200 + (i * 25),
                        "valve1": (i % 2 == 0),
                        "valve2": (i % 2 == 1),
                        "valve3": False,
                        "valve4": False,
                        "valve5": False,
                        "valve6": False,
                        "valve7": False,
                        "valve8": False,
                        "valve9": False,
                        "valve10": False,
                        "airpump1": (i % 2 == 0),
                        "airpump2": (i % 2 == 1),
                        "pressureSP": 1.0 + (i * 0.5),
                        "oxySP": 1.0 + (i * 0.3),
                        "pressureKp": 1.0 + (i * 0.1),
                        "pressureKi": 1.0 + (i * 0.05),
                        "pressureKd": 1.0 + (i * 0.02),
                        "oxyKp": 1.0 + (i * 0.1),
                        "oxyKi": 1.0 + (i * 0.05),
                        "oxyKd": 1.0 + (i * 0.02),
                        "pump2Dir": True,
                        "pump1Dir": True,
                        "tube_bore": 1 + i,
                        "pump_2_speed_ratio": 1.0 + (i * 0.1),
                        "wristCmd": i,
                        "transTimeSec": 2 + i,
                    }
                }
            }
            if not self.send_json(line):
                return False

            ack = self.wait_for_command("sequence_ack", timeout=10.0)
            if not ack:
                print_with_timestamp(f"❌ No sequence_ack for line {i}")
                return False
            print_with_timestamp(f"✅ sequence_ack for line {i}")

        # 4) Expect sequence_complete from AlphaCommsManager
        print_with_timestamp("Waiting for sequence_complete...")
        if not self.wait_for_command("sequence_complete", timeout=15.0):
            print_with_timestamp("❌ No sequence_complete received")
            return False
        print_with_timestamp("✅ sequence_complete received")

        # 5) Verify SequenceController received completion and started execution
        if not self.wait_for_log_contains("SequenceController: Received sequence completion event", timeout=10.0):
            print_with_timestamp("❌ SequenceController did not log completion event receipt")
            return False
        print_with_timestamp("✅ SequenceController received completion event")

        # 6) Verify execution of each line
        for i in range(3):
            if not self.wait_for_log_contains(f"Executing sequence {i}", timeout=15.0):
                print_with_timestamp(f"❌ Did not see execution start for sequence {i}")
                return False
            if not self.wait_for_log_contains(f"Dispatched sequence {i} commands", timeout=15.0):
                print_with_timestamp(f"❌ Did not see dispatch log for sequence {i}")
                return False
            print_with_timestamp(f"✅ SequenceController executed line {i}")

        # 7) Verify completion of execution
        if not self.wait_for_log_contains("SequenceController: All sequences completed", timeout=20.0):
            print_with_timestamp("❌ Did not see final completion log from SequenceController")
            return False
        print_with_timestamp("✅ SequenceController reported all sequences completed")

        print_with_timestamp("=== All checks passed ===")
        return True


def main():
    import sys
    port = 'COM4'
    baudrate = 115200
    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        baudrate = int(sys.argv[2])

    t = SequenceControllerTester(port=port, baudrate=baudrate)
    if not t.connect():
        return 1
    try:
        ok = t.run()
        return 0 if ok else 2
    finally:
        t.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())



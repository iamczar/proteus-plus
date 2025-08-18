#!/usr/bin/env python3
import argparse
import json
import time
import sys

import serial  # pyserial


def send_reset(port: str, baudrate: int = 115200, wait: bool = False, wait_timeout: float = 30.0) -> int:
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            time.sleep(1)

            cmd = {
                "message_source": "proteus_test",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "message": {
                    "command": "auto_sampler_cmd",
                    "sampler_id": 1,
                    "cmd": 1,  # RESET
                    "hold_time": 0,
                    "delay_seconds": 0,
                },
            }

            payload = json.dumps(cmd) + "\n"
            ser.write(payload.encode("utf-8"))
            print("Sent RESET to AutoSampler 1")

            if not wait:
                return 0

            print("Waiting for acknowledgement/state ...")
            start = time.time()
            while time.time() - start < wait_timeout:
                try:
                    line = ser.readline().decode("utf-8").strip()
                    if not line:
                        continue
                    msg = json.loads(line)
                    # Flatten inner message if present
                    if isinstance(msg, dict) and isinstance(msg.get("message"), dict):
                        flat = dict(msg)
                        flat.update(msg["message"])  # promote inner
                    else:
                        flat = msg

                    if not isinstance(flat, dict):
                        continue

                    if (
                        flat.get("message_source") == "auto_sampler"
                        and flat.get("sampler_id") == 1
                        and (
                            flat.get("status") in {"command_received", "moving_to_bottom", "waiting_for_command"}
                            or flat.get("event") == "error"
                        )
                    ):
                        print("Received:", json.dumps(flat))
                        return 0
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"Read error: {e}")
                    break

            print("Timeout waiting for acknowledgement/state")
            return 1

    except Exception as e:
        print(f"Failed to send RESET: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Send RESET to AutoSampler 1")
    parser.add_argument("--port", "-p", default="COM4", help="Serial port (default: COM4)")
    parser.add_argument("--baudrate", "-b", type=int, default=115200, help="Baudrate (default: 115200)")
    parser.add_argument("--wait", action="store_true", help="Wait for acknowledgement/state")
    parser.add_argument("--timeout", type=float, default=30.0, help="Wait timeout seconds (default: 30)")
    args = parser.parse_args()

    return send_reset(args.port, args.baudrate, args.wait, args.timeout)


if __name__ == "__main__":
    sys.exit(main())



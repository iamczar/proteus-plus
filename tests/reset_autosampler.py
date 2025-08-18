#!/usr/bin/env python3
import argparse
import json
import time
import sys

import serial  # pyserial


def send_reset(port: str, baudrate: int = 115200) -> int:
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
            print("Listening for AutoSampler 1 messages (press Ctrl+C to exit)...")

            while True:
                try:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
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

                    # Filter: only auto_sampler messages for sampler 1
                    if flat.get("message_source") != "auto_sampler" or flat.get("sampler_id") != 1:
                        continue

                    # Print concise status line
                    status = flat.get("status") or flat.get("event") or ""
                    state = flat.get("state") or ""
                    sensor = flat.get("sensor_state") or ""
                    desc = flat.get("description") or flat.get("details") or ""
                    ts = flat.get("timestamp")
                    if isinstance(ts, (int, float)):
                        ts_str = time.strftime("%H:%M:%S", time.localtime(ts))
                    else:
                        ts_str = str(ts) if ts else time.strftime("%H:%M:%S")
                    print(f"[{ts_str}] sampler=1 status={status} state={state} sensor={sensor} {desc}")
                except json.JSONDecodeError:
                    continue
                except KeyboardInterrupt:
                    print("\nExiting...")
                    return 0
                except Exception as e:
                    print(f"Read error: {e}")
                    time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nExiting...")
        return 0
    except Exception as e:
        print(f"Failed to send RESET: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Send RESET to AutoSampler 1 and follow messages")
    parser.add_argument("--port", "-p", default="COM4", help="Serial port (default: COM4)")
    parser.add_argument("--baudrate", "-b", type=int, default=115200, help="Baudrate (default: 115200)")
    args = parser.parse_args()

    return send_reset(args.port, args.baudrate)


if __name__ == "__main__":
    sys.exit(main())



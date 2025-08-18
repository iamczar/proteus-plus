#!/usr/bin/env python3
import argparse
import json
import sys
import time

import serial  # pyserial


CMD_MAP = {
    "stop": 0,
    "reset": 1,
    "run": 2,
    "delayed_run": 3,
}


def parse_cmd(cmd_str: str) -> int:
    s = cmd_str.strip().lower()
    if s.isdigit():
        return int(s)
    if s in CMD_MAP:
        return CMD_MAP[s]
    raise ValueError(f"Unknown command: {cmd_str} (use one of: {', '.join(CMD_MAP.keys())} or 0/1/2/3)")


def send_cmd(port: str, baudrate: int, sampler_id: int, cmd: int, hold_time: float, delay_seconds: int, follow: bool) -> int:
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            time.sleep(1)

            payload = {
                "message_source": "proteus_test",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "message": {
                    "command": "auto_sampler_cmd",
                    "sampler_id": sampler_id,
                    "cmd": cmd,
                    "hold_time": hold_time,
                    "delay_seconds": delay_seconds,
                },
            }

            ser.write((json.dumps(payload) + "\n").encode("utf-8"))
            print(f"Sent auto_sampler_cmd: sampler={sampler_id} cmd={cmd} hold={hold_time}h delay={delay_seconds}s")

            if not follow:
                return 0

            print("Following AutoSampler messages (Ctrl+C to exit)...")
            while True:
                try:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    msg = json.loads(line)
                    # Flatten nested system messages
                    if isinstance(msg, dict) and isinstance(msg.get("message"), dict):
                        flat = dict(msg)
                        flat.update(msg["message"])  # promote inner fields
                    else:
                        flat = msg

                    if not isinstance(flat, dict):
                        continue

                    # Filter: only auto_sampler messages for the requested sampler
                    if flat.get("message_source") != "auto_sampler" or flat.get("sampler_id") != sampler_id:
                        continue

                    status = flat.get("status") or flat.get("event") or ""
                    state = flat.get("state") or ""
                    sensor = flat.get("sensor_state") or ""
                    desc = flat.get("description") or flat.get("details") or ""
                    ts = flat.get("timestamp")
                    if isinstance(ts, (int, float)):
                        ts_str = time.strftime("%H:%M:%S", time.localtime(ts))
                    else:
                        ts_str = str(ts) if ts else time.strftime("%H:%M:%S")
                    print(f"[{ts_str}] sampler={sampler_id} status={status} state={state} sensor={sensor} {desc}")
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
        print(f"Failed to send command: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Send command to a specific AutoSampler and optionally follow output")
    parser.add_argument("--port", "-p", default="COM4", help="Serial port (default: COM4)")
    parser.add_argument("--baudrate", "-b", type=int, default=115200, help="Baudrate (default: 115200)")
    parser.add_argument("--sampler-id", "-s", type=int, default=1, help="Sampler ID (default: 1)")
    parser.add_argument("--cmd", "-c", required=True, help="Command: stop/reset/run/delayed_run or 0/1/2/3")
    parser.add_argument("--hold", type=float, default=0.0, help="Hold time in hours (for RUN/DELAYED_RUN)")
    parser.add_argument("--delay", type=int, default=0, help="Delay seconds (for DELAYED_RUN)")
    parser.add_argument("--no-follow", action="store_true", help="Do not follow messages after sending")

    args = parser.parse_args()
    cmd = parse_cmd(args.cmd)
    follow = not args.no_follow

    return send_cmd(args.port, args.baudrate, args.sampler_id, cmd, args.hold, args.delay, follow)


if __name__ == "__main__":
    sys.exit(main())



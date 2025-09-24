#!/usr/bin/env python3
"""
Simple serial sniffer for LEM identification and debugging.

Usage:
  python lem_serial_sniffer.py COM5 --baud 115200 --timeout 5

Notes:
  - Prints every raw line received from the device with timestamps.
  - Accepts both CR and LF line endings and trailing commas.
  - Highlights lines that match LEM signatures (command id 1001 or 1515).
"""

import argparse
import sys
import time
from datetime import datetime

try:
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except Exception as exc:  # pragma: no cover
    print("pyserial is required. Install with: pip install pyserial", file=sys.stderr)
    raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LEM serial sniffer")
    parser.add_argument("port", help="Serial port (e.g. COM5, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Read timeout in seconds; sniffer exits after this with code 0 (default: 10)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available serial ports and exit",
    )
    return parser.parse_args()


def list_available_ports() -> None:
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports detected.")
        return
    print("Available serial ports:")
    for p in ports:
        print(f"  - {p.device}  ({p.description})")


def classify_line(line: str) -> str:
    """Return a short classification tag for the line content."""
    # Normalize commas and split tokens; tolerate trailing comma
    try:
        tokens = [t for t in line.strip().strip(",").split(",") if t != ""]
        if len(tokens) >= 3:
            # token[2] is command id in both request (1001) and report (1515)
            cmd = tokens[2]
            if cmd == "1001":
                return "LEM-REQ"
            if cmd == "1515":
                return "LEM-REPORT"
        return "TEXT/CSV"
    except Exception:
        return "TEXT/CSV"


def main() -> int:
    args = parse_args()

    if args.list:
        list_available_ports()
        return 0

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.1)
    except Exception as exc:
        print(f"Failed to open {args.port}: {exc}", file=sys.stderr)
        return 2

    print(
        f"Opened {args.port} at {args.baud} baud. Listening up to {args.timeout}s...",
        flush=True,
    )

    start = time.time()
    buffer = bytearray()

    try:
        while True:
            if (time.time() - start) > args.timeout:
                print("Timeout reached; exiting.")
                return 0

            chunk = ser.read(256)
            if not chunk:
                continue
            buffer.extend(chunk)

            # Split on either CR or LF; keep remainder in buffer
            while True:
                for sep in (b"\n", b"\r"):
                    idx = buffer.find(sep)
                    if idx != -1:
                        line_bytes = buffer[:idx]
                        # Drop all sequential newline bytes
                        while idx < len(buffer) and buffer[idx:idx+1] in (b"\n", b"\r"):
                            idx += 1
                        buffer = buffer[idx:]
                        line = line_bytes.decode(errors="replace").strip()
                        if line == "":
                            break
                        tag = classify_line(line)
                        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[{ts}] [{tag}] {line}")
                        break
                else:
                    # No separator found
                    break
    except KeyboardInterrupt:
        print("Interrupted by user.")
        return 0
    finally:
        try:
            ser.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())



"""
Open a serial port by COM name and display incoming messages.

Usage:
  python open_serial_port_test.py COM4 [BAUD] [--read-seconds 5]

Notes:
  - If --read-seconds <= 0 (default), it reads indefinitely until Ctrl+C.
  - If --read-seconds > 0, it reads for that many seconds and exits.

Examples:
  python open_serial_port_test.py COM4
  python open_serial_port_test.py /dev/ttyUSB0 115200 --read-seconds 10
"""

import argparse
import sys
import time

try:
    import serial  # pyserial
except Exception as e:
    print(f"pyserial not installed or import failed: {e}")
    sys.exit(2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Open a serial port by COM name and optionally read.")
    parser.add_argument("port", help="Serial port (e.g., COM4 or /dev/ttyUSB0)")
    parser.add_argument("baud", nargs="?", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--read-seconds", dest="read_seconds", type=float, default=0.0, help="If <=0, read indefinitely; if >0, read for N seconds")
    args = parser.parse_args()

    ser = None
    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.2)
        print(f"Opened serial port {args.port} @ {args.baud}")

        # Reader: indefinite by default; time-bound if --read-seconds > 0
        start = time.time()
        buffer = b""
        print(
            "Reading indefinitely... (Ctrl+C to stop)"
            if args.read_seconds <= 0
            else f"Reading for {args.read_seconds} seconds... (Ctrl+C to stop)"
        )
        while True:
            if args.read_seconds > 0 and (time.time() - start >= args.read_seconds):
                break
            try:
                waiting = ser.in_waiting
            except Exception:
                waiting = 0
            if waiting:
                try:
                    chunk = ser.read(waiting)
                    if chunk:
                        buffer += chunk
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            try:
                                print(line.decode("utf-8", errors="replace"))
                            except Exception:
                                print(repr(line))
                except Exception:
                    pass
            time.sleep(0.02)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        print(f"Failed to open or read from serial port: {e}")
        return 1
    finally:
        if ser is not None:
            try:
                ser.close()
                print("Closed serial port")
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())



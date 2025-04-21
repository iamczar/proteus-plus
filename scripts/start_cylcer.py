import subprocess
import argparse
import sys

def run_main_script(port):
    print(f"[INFO] Running main.py on device via {port}...")

    try:
        result = subprocess.run(
            ["ampy", "--port", port, "run", "main.py"],
            capture_output=True,
            text=True,
            check=True
        )
        print("[SUCCESS] main.py started.\n")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("[ERROR] Failed to run main.py")
        print("STDOUT:\n", e.stdout)
        print("STDERR:\n", e.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run main.py on MicroPython board using ampy.")
    parser.add_argument("--port", required=True, help="Serial port (e.g., COM5 or /dev/ttyACM0)")
    args = parser.parse_args()

    run_main_script(args.port)

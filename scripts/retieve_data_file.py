import subprocess
import argparse
import os
import sys

DEFAULT_REMOTE_DIR = "/sd/session_logs"
LOCAL_DIR = "./data"

def list_remote_files(port, remote_dir):
    try:
        result = subprocess.run(
            ["ampy", "--port", port, "ls", remote_dir],
            capture_output=True,
            text=True,
            check=True
        )
        return [f.strip() for f in result.stdout.splitlines()]
    except subprocess.CalledProcessError as e:
        print("[ERROR] Failed to list files:", e.stderr)
        return []

def download_files(port, remote_dir, files):
    os.makedirs(LOCAL_DIR, exist_ok=True)

    for file in files:
        filename = os.path.basename(file)
        local_path = os.path.join(LOCAL_DIR, filename)
        print(f"[INFO] Downloading {file} → {local_path}")
        try:
            with open(local_path, "wb") as f:
                subprocess.run(
                    ["ampy", "--port", port, "get", f"{remote_dir}/{filename}"],
                    stdout=f,
                    check=True
                )
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to download {filename}:", e.stderr)

def main():
    parser = argparse.ArgumentParser(description="Retrieve files from /sd/session_logs using ampy.")
    parser.add_argument("--port", required=True, help="Serial COM port (e.g., COM5)")
    args = parser.parse_args()

    port = args.port
    remote_dir = DEFAULT_REMOTE_DIR

    print(f"[INFO] Connecting to {port} and retrieving files from {remote_dir}...")

    files = list_remote_files(port, remote_dir)
    if not files:
        print("[INFO] No files found.")
        return

    download_files(port, remote_dir, files)
    print("[DONE] All files downloaded.")

if __name__ == "__main__":
    main()

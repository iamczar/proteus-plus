# LIBRARIES
import serial
import csv
import threading
import argparse
import time
import json
import sys
import subprocess
import os

stop_event = threading.Event()  # Event to control thread termination

# Create the argument parser
parser = argparse.ArgumentParser(description="ALFI sequencer, ALFONSO V03w2 (wip).")

# Add arguments without mutual exclusivity
parser.add_argument(
    '-s', '--serial_config',
    type=str,
    help='Path to the serial config file (default: serial_config.csv)',
    default='serial_config.csv',
    metavar=''
)
parser.add_argument(
    '-u', '--moduid',
    type=str,
    help='Specify the module UID',
    metavar=''
)

# Parse arguments
args = parser.parse_args()

def find_module_serial(moduid):
    """Find the COM port for the given module UID."""
    print(f"Searching for module with moduid {moduid}")
    full_path = args.serial_config
    with open(full_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['moduid'] == str(moduid):
                try:
                    return row['port']  # Return COM port
                except KeyError:
                    print(f"Missing required field in serial config: {row}")
    print(f"Module with moduid {moduid} not found")
    return None

def delete_all_logs(com_port):
    """List and copy all files from the session logs folder."""
    source_folder = "/sd/session_logs"
    try:
        # List all files in the folder
        result = subprocess.run(
            ["ampy", "--port", com_port, "ls", source_folder],
            capture_output=True,
            text=True,
            check=True
        )
        source_files = result.stdout.strip().splitlines()

        if not source_files:
            print(f"No files found in {source_folder}")
            return

        # Delete each file
        for source_file in source_files:
            source_file_name = os.path.basename(source_file)
            
            file_path = f"{source_folder}/{source_file_name}"
            print(f"Deleting file: {file_path}")
            subprocess.run(
                ["ampy", "--port", com_port, "rm", file_path],
                check=True
            )
        print("All files deleted successfully.")
            
    except subprocess.CalledProcessError as e:
        print(f"Error during deletion process: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        
         
def main():
    try:
        print(f"------------------------------ Delete Session Logs -----------------------------------------")
        com_port = find_module_serial(args.moduid)
        if com_port is None:
            print(f"Failed to find serial connection for moduid {args.moduid}")
            sys.exit(1)
        print(f"------------------------------ COM Port: {com_port} -----------------------------------------")

        # Start the delete process in a thread
        thread = threading.Thread(target=delete_all_logs, args=(com_port,))
        thread.start()
        thread.join()  # Ensure the main thread waits for deletion to complete

    except Exception as e:
        print(f"----------------------- Error: {e} -------------------------------------")


if __name__ == '__main__':
    main()
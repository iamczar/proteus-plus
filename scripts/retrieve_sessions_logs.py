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

parser.add_argument(
    '-t', '--target_folder',
    type=str,
    help='Specify the target folder to save the logs',
    metavar=''
)

parser.add_argument(
    '-d', '--data_folder',
    type=str,
    help='Specify the target folder to save the logs',
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

def copy_all_session_logs(com_port, target_folder,data_destination_filepath):
    """List and copy all files from the session logs folder."""
    source_folder = "/sd/session_logs"
    try:
        # List all files in the source folder
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

        # Copy each file
        for source_file in source_files:
            # Extract only the file name
            source_file_name = os.path.basename(source_file)
            destination_file = os.path.join(target_folder, source_file_name)
            print(f"Copying {source_file} to {destination_file}")
            
            # copy file to the desired location
            subprocess.run(
                ["ampy", "--port", com_port, "get", source_file, destination_file],
                check=True
            )
            
            print(f"Copying {source_file} to {data_destination_filepath}")
            # replace copy on the data folder
            subprocess.run(
                ["ampy", "--port", com_port, "get", source_file, data_destination_filepath],
                check=True
            )
            
            # Verify the file was created at the destination
            if os.path.exists(destination_file):
                print(f"File transfer successful: {destination_file}")
            else:
                print(f"File transfer failed or incomplete: {destination_file}")

    except subprocess.CalledProcessError as e:
        print(f"Error retrieving logs via ampy: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        
        
        
def main():
    global keeprunning
    keeprunning = True

    try:
        print(f"------------------------------retrieve session logs-----------------------------------------")
        com_port = find_module_serial(args.moduid)
        if com_port is None:
            print(f"Failed to find serial connection for moduid {args.moduid}")
            sys.exit(1)
        print(f"------------------------------retrieve session log COMPORT: {com_port} -----------------------------------------")

        thread = threading.Thread(target=copy_all_session_logs, args=(com_port,args.target_folder,args.data_folder))
        thread.start()
        
    except Exception as e:
        print(f"-----------------------retrieve session logs: main {e}-------------------------------------")


if __name__ == '__main__':
    main()
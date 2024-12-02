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

def validate_line(line):
    try:
        # Split the line into elements
        elements = line.split(",")      
        # Check if the number of elements matches the expected format
        if len(elements) != 26:
            print(f"line not 26: {elements}")
            return False
        
        return line
    except Exception as e:
        return False
    

def retrieve_file_over_serial(com_port, target_file, data_file):
    """
    Continuously requests data from the device over serial and writes it to files.

    :param com_port: The COM port to communicate with the device.
    :param target_file: The path to save the retrieved file in the target folder.
    :param data_file: The path to save the retrieved file in the destination folder.
    """
    try:
        
        print(f"target_file:{target_file}")
        print(f"data_file:{data_file}")
        
        # Check if files exist and delete them
        if os.path.exists(target_file):
            print(f"Deleting existing file: {target_file}")
            os.remove(target_file)

        if os.path.exists(data_file):
            print(f"Deleting existing file: {data_file}")
            os.remove(data_file)
        
        # Open the serial connection
        with serial.Serial(com_port, baudrate=115200, timeout=2) as ser:
            print("Connected to the device.")

            # Open the files for writing
            with open(target_file, "a") as target, open(data_file, "a") as dest:
                print("Opened files for writing.")

                while True:
                    # Send the RETRIEVE_DATA command
                    ser.write(b"4,0\n")
                    print("Sent RETRIEVE_DATA command.")

                    # Read a line of data
                    line = ser.readline().decode("utf-8").strip()

                    if line == "555":  # Transfer complete signal
                        print("File transfer complete.")
                        break

                    # Check if the line starts with the expected header
                    if line.startswith("f,"):
                        # Remove the "f," prefix before writing
                        cleaned_line = line[2:]  # Remove "f," prefix
                        
                        valid_line = validate_line(cleaned_line)
                        if False != valid_line:
                            print(f"Valid line received: {valid_line}")
                            target.write(valid_line + "\n")
                            dest.write(valid_line + "\n")
                    else:
                        print(f"Ignored invalid line: {line}")

                    time.sleep(0.01)  # Small delay to prevent spamming

            print(f"File saved to target: {target_file} and destination: {data_file}")

    except Exception as e:
        print(f"Error during file retrieval: {e}")

def copy_all_session_logs(com_port, target_folder,data_destination_filepath,module_id):
    """
    Manages the file transfer from the device over serial.

    :param com_port: The COM port to communicate with the device.
    :param target_folder: Folder to save retrieved logs.
    :param data_destination_filepath: Path to save logs in the data folder.
    """
    try:
        # Construct file paths
        target_file = os.path.join(target_folder, f"{module_id}_data.csv")
        # data_file = os.path.join(data_destination_filepath, f"{module_id}_data.csv")
        print("Starting log retrieval over serial...")
        retrieve_file_over_serial(com_port, target_file, data_destination_filepath)

    except Exception as e:
        print(f"Error during log retrieval: {e}")
        
        
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

        thread = threading.Thread(target=copy_all_session_logs, 
                                  args=(com_port,args.target_folder,args.data_folder,args.moduid))
        thread.start()
        thread.join()  # Ensure the thread completes
        
    except KeyboardInterrupt:
        stop_event.set()
        print("Interrupted by user.")
    except Exception as e:
        print(f"Error in main: {e}")


if __name__ == '__main__':
    main()
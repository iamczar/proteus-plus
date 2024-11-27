# LIBRARIES
import serial
import csv
import threading
import argparse
import time
import json
import sys

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



######################################################## MODULES ########################################################

def find_module_serial(moduid):
    print(f"Searching for module with moduid {moduid}")
    serials = []
    full_path = args.serial_config
    #print(f"------------------------------------find_module_serial: full_path: {full_path}----------------------------------")
    with open(full_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['moduid'] == str(moduid):
                try:
                    # port = row['port']
                    # baudrate = int(row['baud_rate'])
                    #print(f"find_module_serial: port: {port}")
                    #print(f"find_module_serial: baudrate: {baudrate}")

                    ser = serial.Serial(port=row['port'], baudrate=int(row['baud_rate']), timeout=int(row['timeout']))
                    ser.moduid = int(row['moduid'])
                    serials.append(ser)
                except (ValueError, serial.SerialException) as e:
                    print(f"An error occurred while setting up the serial port: {e}")
    print(f"Module with moduid {moduid} not found")
    return serials


def serial_listen_thread(serial_conn):
    buffer = ""  # Initialize the buffer for incoming data
    timeout = 10  # Timeout in seconds
    start_time = time.time()  # Record the start time
    try:
        while keeprunning:
            # Read available bytes from the serial port
            incoming_data = serial_conn.read(1024).decode('utf-8')  # Adjust the buffer size as needed
            buffer += incoming_data  # Append to the buffer

            # Process complete lines
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)  # Split on the first newline
                rx_data = line.strip()  # Remove leading/trailing whitespaces
                print(f"SEND_STOP:serial_listen_thread: Received: {repr(rx_data)}")
                if rx_data == "111":
                    print(f"ACK RX:{rx_data}serial_listen_thread:closing serial port and terminating the thread")
                    serial_conn.close()
                    stop_event.set()
                    break
                else:
                    serial_conn.write(("1,0\n").encode()) # keep sending stop
                    #print(f"SEND_STOP:serial_listen_thread: Sent: 1,0")
                        # Check for timeout
            
            if time.time() - start_time >= timeout:
                print("SEND_STOP:serial_listen_thread: Timeout reached, shutting down.")
                serial_conn.close()
                stop_event.set()
                return  # Exit the thread  
            
            time.sleep(0.1)  # Avoid busy waiting
    except Exception as e:
        print(f"SEND_STOP: serial_listen_thread: {e}")

def main():
    global keeprunning
    keeprunning = True

    try:
        print(f"------------------------------SEND_STOP-----------------------------------------")
        serial = find_module_serial(args.moduid)
        if not serial:
            print(f"Failed to find serial connection for moduid {args.moduid}")
            sys.exit(1)

        thread = threading.Thread(target=serial_listen_thread, args=(serial))
        thread.start()
        
    except Exception as e:
        print(f"-----------------------SEND_STOP: main {e}-------------------------------------")


if __name__ == '__main__':
    main()
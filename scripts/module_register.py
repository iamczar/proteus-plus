'''
scan the available serial ports, and attempt to find devices that are Arduinos.

| MODULE | TYPE        | SERIALNUMBER | COMPORT | 
|--------|-------------|--------------|---------|
| 2501   | Circulation | 123456       | COM3    |
| 3701   | LEM         | 123456       | COM4    |
| 3702   | LEM         | 123456       | COM5    |
| 2504   | Circulation | 123456       | COM6    | 

1. scan the available serial ports, make a list of any Arduinos found.  (scan_ports)
2. open a serial connection to the Arduino, which will send a 1001 state request, which will contain its moduid.
3. compile a row for a serial config.csv file.
4. Save the updated config file.

'''

import serial.tools.list_ports
import csv
import os
import argparse
import time

parser = argparse.ArgumentParser(description='Register Arduino modules')
parser.add_argument('--debug', '-d', action='store_true', help='Print debug messages')
parser.add_argument('--skip', '-s', action='store_true', help='Skip the confirmation prompt')
parser.add_argument('--config', '-c', help='Specify the path to the serial_config file')
args = parser.parse_args()

BAUDRATE = 115200
TIMEOUT = 1
cwd = os.getcwd()
CONFIG_FILE = args.config if args.config else os.path.join(cwd, 'serial_config.csv')
debug = args.debug
modules = {}

class Module:
    def __init__(self, moduid, serial_number, comport):
        self.moduid = moduid
        self.serial_number = serial_number
        self.comport = comport

def scan_ports():
    ports = list(serial.tools.list_ports.comports())
    if debug:
        print(ports)
    arduino_ports = [port for port in ports if 'USB Serial Device' in port.description]
    if debug:
        for port in ports:
            print(port.description)
    return arduino_ports

def find_moduid(port):
    try:
        ser = serial.Serial(port.device, BAUDRATE, timeout=TIMEOUT)
    except SerialException as e:
        print(f"Could not open port: {e}")
        return None

    try:
        for _ in range(100):  # Attempt to read serial port 10 times
            line = ser.readline().decode('utf-8').strip()
            print(f"Read line: {line}")
            
            # Check if line matches the expected pattern
            if line.startswith("0,") and len(line.split(',')) >= 5:
                moduid = line.split(',')[1]
                if moduid.isdigit():  # Validate moduid is numeric
                    return moduid
            time.sleep(0.1)
        
            print("No matching pattern found in serial data.")
        return None
    except Exception as e:
        print(f"Error reading from port: {e}")
        return None
    finally:
        ser.close()

def main():
    global CONFIG_FILE

    print('The target serial_config file is', CONFIG_FILE)
    if not args.skip:
        print('Is this correct? (y/n)')
    while True:
        if args.skip:
            break
        response = input()
        if response.lower() == 'y':
            break
        elif response.lower() == 'n':
            CONFIG_FILE = input('Enter the path to the serial_config file: ')
            break
        else:
            print('Invalid input. Please enter "y" or "n".')
    print('Scanning for Arduino modules...')


    ports = scan_ports()
    for port in ports:
        modules[port] = Module(find_moduid(port), port.serial_number, port.device)

    
    try:
        with open(CONFIG_FILE, 'w') as f:
            f.write('port,baud_rate,timeout,moduid\n')
    except IOError as e:
        print(f"Could not write headers to file: {e}")
        return

    for module in modules:
        newrow = ','.join([str(modules[module].comport), str(BAUDRATE), str(TIMEOUT), str(modules[module].moduid)])
        try:
            with open(CONFIG_FILE, 'a') as f:
                f.write(newrow)
                print(newrow)
                f.write('\n')
        except IOError as e:
            if debug:
                print(f"Could not write to file: {e}")
    
    print('Done, written to', CONFIG_FILE)

if __name__ == '__main__':
    main()


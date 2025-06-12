# LIBRARIES
import serial
import csv
import datetime
import os
from datetime import datetime
import threading
import argparse
import sys
import time
import json

VERSION = "V03w2"


###########################################################################################################
############################################# LOAD CONFIG ################################################
moduid = None

config = {}

def load_config():
    global config
    config_file = 'configs/config.json' 
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            #print('Alf loaded config: ', config)
    except FileNotFoundError:
        print(f"ALF: Configuration file {config_file} not found.")
    except json.JSONDecodeError:
        print(f"ALF: Configuration file {config_file} is not a valid JSON file.")

load_config()

############################################ ARGPARSE ############################################################################

parser = argparse.ArgumentParser(description="ALFI sequencer, ALFONSO V03w2 (wip).")

parser.add_argument('--debug', action='store_true', help='debug mode')
parser.add_argument('-q','--seq_csv', type=str, help='seQuence.csv', metavar='')
parser.add_argument('-l','--log_csv', type=str, help='log.csv', metavar='')
parser.add_argument('-b','--baud', type=int, help='baud', default=115200, metavar='')
parser.add_argument('-p','--pause', action='store_true', help='pause', default=False)
parser.add_argument('-m','--module_csv', type=str, help='modules.csv', default='serial_config.csv', metavar='')
parser.add_argument('-d','--data_csv', type=str, help='data.csv', metavar='')
parser.add_argument('-e','--experiment_file_path', type=str, help='experiment.csv', metavar='')
parser.add_argument('-i','--index', type=int, help='index', metavar='')
                    
target = parser.add_mutually_exclusive_group()
target.add_argument('-s','--serial_config', type=str, help='serial config file', default= 'serial_config.csv', metavar='')
target.add_argument('-c','--port', type=str, help='port', metavar='')
target.add_argument('-u','--moduid', type=int, help='moduid', metavar='')

args = parser.parse_args()

debug = args.debug
#if debug:
    #print(args)

############################################ COMMUNICATION PROTOCOL POSITIONS ########################################################




COMPOS = {
    "circFlow": 0,
    "pressureFlow": 1,
    "valve1": 2,
    "valve2": 3,
    "valve3": 4,
    "valve4": 5,
    "valve5": 6,
    "valve6": 7,
    "valve7": 8,
    "valve8": 9,
    "valve9": 10,
    "valve10": 11,
    "airpump1": 12,
    "airpump2": 13,
    "pressureSP": 14,
    "oxySP": 15,
    "pressureKp": 16,
    "pressureKi": 17,
    "pressureKd": 18,
    "oxyKp": 19,
    "oxyKi": 20,
    "oxyKd": 21,
    "pump2Dir": 22,
    "pump1Dir": 23,
    "tube_bore": 24,
    "pump_2_speed_ratio": 25,
    "ascmds1": 26,
    "ascmds2": 27,
    "ascmds3": 28,
    "wristCmd": 29
}

TASKS = {
    "OXY1": 1,
    "OXY2": 2,
    "OXY3": 3,
    "OXY4": 4,
    "FLOW": 5,
    "PRESSURE": 6,
    "REPORT": 15
}

TRANSTYPE = {
    "TIME": 46,
    "OXYGEN": 47,
    "PRESSURE": 48,
    "TEMPERATURE": 49,
    "MODWAKE": 50,
    "VOLUME": 51,
    "LIQUIDADDITION": 52
}

COMMANDS = {
    "MODSTATEREQUEST": 1001,
    "PCSTATEDISPATCH": 1002,
    "MODSTATEREPLY": 1003,
    "MODDATAREPORT": 1515
}

REPPOS = {
    "NULLLEADER": 0,
    "MODUID": 1,
    "COMMAND": 2,
    "STATEID": 3,
    "OXYMEASURED": 4,
    "PRESSUREMEASURED": 5,
    "FLOWMEASURED": 6,
    "TEMPMEASURED": 7,
    "CIRCPUMPSPEED": 8,
    "PRESSUREPUMPSPEED": 9,
    "NULLTRAILER": 10
}

OXYMEASUREMENT = {
    "STATUS": 3,
    "UMOLAR": 4,
    "MBAR": 5,
    "AIRSAT": 6,
    "TEMPSAMPLE": 7,
    "SIGNALINTENSITY": 8,
    "AMBIENTLIGHT": 9,
    "PERCENTO2": 10
}


######################################################## MODULES ########################################################

class Module:
    def __init__(self):
        self.sequence = []
        self.moduid = None
        self.sequence_stage = 0
        self.stateID = None

modules=[]

def load_sequence(moduid, debug=False):

    dir_path = os.path.dirname(os.path.realpath(__file__))
    if args.seq_csv:
        csv_file_path = args.seq_csv
    else: 
        csv_file_path = os.path.join(dir_path, f"{moduid}_sequence.csv")

    # csv_file_path = os.path.join(dir_path, args.seq_csv)
    data_matrix = []

    try:
        # Check if file exists
        if not os.path.exists(csv_file_path):
            print(f"Alert: File {csv_file_path} does not exist.")
            return None

        # Load data from CSV
        with open(csv_file_path, newline='', encoding='utf-8-sig' ) as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            header = next(reader)  # Assuming the first row contains column headers

            # # Check if keys in COMPOS match with the headers in the CSV file
            # for key, value in COMPOS.items():
            #     if header[value] != key:
            #         print(f"Header for column {value} does not match key {key} in COMPOS.")
            #         return None
            # else:
                # Load data rows into the matrix
            for row in reader:
                data_matrix.append(row)

            # Print the loaded data matrix
            if debug:
                print(f"Loaded data from {csv_file_path}:")
                for entry in data_matrix:
                    print(entry)

    except Exception as e:
        print(f"ALF: An error occurred while loading the sequence for module {moduid}: {e}")

    return data_matrix

def get_or_create_module(moduid):
    # Look for module with given moduid, if not found create it
    module = next((m for m in modules if m.moduid == moduid), None)
    if module is None:
        module = Module()
        module.moduid = moduid
        module.sequence = []
        module.sequence_stage = ((args.index)-1) if args.index else 0
        modules.append(module)
        print(f"ALF: Created new module: {moduid}")
        module.sequence=load_sequence(moduid)
        if debug:
            print(module.sequence)

    return module

def log_and_report(moduid, line, ser):
    try:
        # Determine the log file name
        dir_path = os.path.dirname(os.path.realpath(__file__))
        if args.log_csv:
            log_file_path = args.log_csv
        else: 
            log_file_path = os.path.join(dir_path, f"{moduid}_log.csv")
        # Get the current datetime
        now = datetime.now()

        # Save the line with a datetime to the log file
        with open(log_file_path, 'a', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([now] + [line])

        # Print a message to the console with the timestamp, moduid, and the line
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        #print(f" ALF:  Module {moduid} reported: {line}")
        if "1515" not in line:
            message=(str(timestamp)+str(line[5:0]))
            print(message)
            
    except Exception as e:
        print(f"ALF: An error occurred while logging and reporting for module {moduid}: {e}")


######################################################## COMS ########################################################

buffers = {}

def serial_listen(ser):
    if ser not in buffers:
        buffers[ser] = b''

    try:
        # Read data from the serial port
        data = ser.read(1)
        buffers[ser] += data

        # Check if we have a complete message
        while b'\n' in buffers[ser]:
            # Split the buffer into a complete message and the remainder
            message, buffers[ser] = buffers[ser].split(b'\n', 1)

            # Decode the complete message
            message = message.decode()

            # Process the complete message
            command_control(message, ser)
    except Exception as e:
        pass
        #print(f"An error occurred while listening to the serial port: {e}")

def command_control(message, ser):
    #print(f"command_control:msg:{message}")
    try:
        # Split the message into values
        if debug:
            print(f"Received message: {message}")
        values = message.split(',')
        if debug:
            None
            #print(f"Split message into values: {values}")
        
        # Check if the message contains enough values
        if len(values) >= 3:
            try:
                moduid, command = map(int, values[1:3])
                if debug:
                    print(f"ALF: Extracted moduid and command: {moduid}, {command}")
            except ValueError:
                if debug:
                    print("ALF: Failed to extract moduid and command")
                return
        else:
            if "INFO" in message:
                if "Free" not in message and "out of range" not in message:
                    pass
                    #print(f"ALF: cycler info:{message[33:]}")
            if "ERROR" in message:
                None
                #print(f"cycler error: {message[35:]}")
            if "Memory" in message:
                None
            #else:
            #    print(f"command too short: {message[35:]}")
    except Exception as e:
        print(e)


    get_or_create_module(moduid)
    log_and_report(moduid, message, ser)

    # Call a different function based on the command
    if command == COMMANDS['MODSTATEREQUEST']:
        # if debug:
        #print("Calling handle_mod_state_request")
        handle_mod_state_request(moduid, message, ser)
    elif command == COMMANDS['MODSTATEREPLY']:
        # if debug:
        #print("Calling handle_mod_state_reply")
        handle_mod_state_reply(moduid, message, ser)
    elif command == COMMANDS['MODDATAREPORT']:
        # if debug:
        #print("Calling handle_mod_data_report")
        handle_mod_data_report(moduid, message, ser)

def handle_mod_state_request(moduid, line, ser):
    # Split the line into values
    values = line.split(',')
    #if debug:
    #print(f"parsed command: {values}")

    # Check if the line contains enough values
    if len(values) >= 4:
        moduid, command, transtype= map(int, values[1:4])
        #if debug:
        #print(f"handle_mod_state_request:Extracted moduid and command: {moduid}, {command}, {transtype}")

        # Find the module with the given moduid
        module = next((m for m in modules if m.moduid == moduid), None)
        if module is not None:
            if debug:
                print(f"ALF: handle_mod_state_request:Found module {moduid}")

            if transtype==TRANSTYPE['VOLUME']:   ######################################################### VOLUME TRANSITION 
                # Check if there's a next sequence stage
                if module.sequence_stage + 1 < len(module.sequence):
                    # Update the module's sequence stage
                    module.sequence_stage += 1
                    if debug:
                        print(f"ALF: Updated module's sequence stage to: {module.sequence_stage}")

                    # Get the next sequence
                    next_sequence = module.sequence[module.sequence_stage]
                    if debug:
                        print(f"ALF: Next sequence: {next_sequence}")

                    # Send the sequence to the Arduino
                    next_sequence_str = ','.join(next_sequence)
                    print(f"ALF: sending sequence: {next_sequence_str}")
                    
                    ser.write((next_sequence_str + "\n").encode())
                    if debug:
                        print(f"ALF: Sent next sequence to Arduino: {next_sequence_str}")

                        # Send next state (null), and then exit.

                else:
                    if debug:
                        print ("ALF: No next sequence stage")

            if not args.pause or transtype == TRANSTYPE['MODWAKE']: ######################################## ALL OTHER TRANSITIONS
                # Check if there's a next sequence stage
                if module.sequence_stage + 1 < len(module.sequence):
                    # Update the module's sequence stage
                    module.sequence_stage += 1
                    if debug:
                        print(f"ALF: Updated module's sequence stage to: {module.sequence_stage}")

                    # Get the next sequence
                    next_sequence = module.sequence[module.sequence_stage]
                    if debug:
                        print(f"ALF: Next sequence: {next_sequence}")

                    # Send the sequence to the Arduino
                    next_sequence_str = ','.join(next_sequence)
                    ser.write((next_sequence_str + "\n").encode())
                    if debug:
                        print(f"ALF: Sent next sequence to Arduino: {next_sequence_str}")
                else:
                    if debug:
                        print ("ALF: No next sequence stage")
        else:
            if debug:
                None    #print(f"ALF: Module with moduid {moduid} not found")

def handle_mod_state_reply(moduid, line, ser):

    datavalues = line.split(',')

    # Check if the line contains enough values
    if len(datavalues) >= 4:
        null, moduid, command, current_state_id = map(int, datavalues[:4])

        # Find the module with the given moduid
        module = next((m for m in modules if m.moduid == moduid), None)

        if module is not None:
            # Compare the received reply with the current sequence stage of the module
                sequencevalues=module.sequence[module.sequence_stage].split(',')
                sequencevalues.pop(COMPOS["COMMAND"])
                datavalues.pop(COMPOS["COMMAND"])

                if sequencevalues == datavalues:
                    # Log the match
                    if debug:
                        print(f"ALF: Match in reply for module {moduid}")

                # Call the log_and_report function with the received reply and the current datetime
                log_and_report(line)
        else:
            if debug:
                print(f"ALF: Mismatch in reply for module {moduid}")

            # Resend the state
            next_sequence = module.sequence[module.sequence_stage]
            ser.write(next_sequence.encode())
            log_and_report(next_sequence.strip())

def handle_mod_data_report(moduid, line, ser):
    try:
        # Split the line into values
        values = line.split(',')

        # Determine the log file name
        dir_path = os.path.dirname(os.path.realpath(__file__))
        if args.data_csv:
            log_file_path = args.data_csv
            experiment_file_path = args.experiment_file_path
            
            # print(f"handle_mod_data_report: log_file_path : {log_file_path}")
            # print(f"handle_mod_data_report: experiment_file_path : {experiment_file_path}")
        else: 
            log_file_path = os.path.join(dir_path, f"{moduid}_data.csv")
        # Get the current datetime
        now = datetime.now()

        # Save the line with a datetime to the log file
        with open(log_file_path, 'a', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([now] + values)
            
        # Save the line with a datetime to the secondary log file
        with open(experiment_file_path, 'a', newline='', encoding='utf-8-sig') as secondary_csvfile:
            secondary_writer = csv.writer(secondary_csvfile)
            secondary_writer.writerow([now] + values)

        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        if debug:
            print(f"ALF: {timestamp}: Module {moduid} data: {line}")
    except Exception as e:
        print(f"ALF: An error occurred while handling module data report for module {moduid}: {e}")

def load_serial_ports(filename):
    serials = []
    full_path = filename
    with open(full_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['port'] != '0':
                try:
                    port = row['port']
                    baudrate=int(row['baud_rate'])

                    print(f"ALF: load_serial_ports : port: {port}")
                    print(f"ALF: load_serial_ports : baudrate: {baudrate}")

                    ser = serial.Serial(port=row['port'], baudrate=int(row['baud_rate']), timeout=int(row['timeout']))
                    ser.moduid = int(row['moduid'])
                    serials.append(ser)
                except (ValueError, serial.SerialException) as e:
                    print(f"ALF: An error occurred while setting up the serial port: {e}")
                except FileNotFoundError:
                    print(f"ALF: The file {filename} was not found.")
                except Exception as e:
                    print(f"ALF: An error occurred while loading the serial ports: {e}") 
    return serials

def find_module_serial(moduid):
    if moduid != 1001:
        print(f"ALF: Searching for module with moduid {moduid}")
    if moduid == 1001:
        print(f"ALF: dummy module connected")
    serials = []
    full_path = args.module_csv
    #print(f"ALF: looking up modules configured in {full_path}----------------------------------")
   
    with open(full_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['moduid'] == str(moduid):
                try:
                    port = row['port']
                    baudrate = int(row['baud_rate'])

                    print(f"ALF: connecting to: module {moduid} using port: {port}, baudrate: {baudrate}")

                    ser = serial.Serial(port=row['port'], baudrate=int(row['baud_rate']), timeout=int(row['timeout']))
                    ser.moduid = int(row['moduid'])
                    serials.append(ser)
                except (ValueError, serial.SerialException) as e:
                    print(f"ALF: An error occurred while setting up the serial port: {e}")
    
    #print(f"ALF: Module with moduid {moduid} not found")
    return serials

###################################################### THREADS ########################################################

def serial_listen_thread(ser):
    while keeprunning:
        serial_listen(ser)

def gui_thread():
    while keeprunning:
        pass

###################################################### MAIN ########################################################

def main():
    global keeprunning
    keeprunning = True

    # Load serial ports
    if args.port:
        serials = []
        print("args.port") 
        print(args.port) 
        print("args.baud")
        print(args.baud)
        ser = serial.Serial(port=args.port, baudrate=args.baud, timeout=1)
        serials.append(ser)
    elif args.moduid:
        #print(f"ALF: main:args.moduid: {args.moduid}")
        serials= find_module_serial(args.moduid)
    else:
        serials = load_serial_ports(args.serial_config)

    # Define threads
    for ser in serials:
        thread = threading.Thread(target=serial_listen_thread, args=(ser,))
        thread.start()

    # thread=threading.Thread(target=gui_thread)
    # thread.start()

    # For exit.
    try:
        while keeprunning:
            line=sys.stdin.readline().strip()
            if line == "exit":
                keeprunning = False
                print("ALF: Exiting...")
            line=sys.stdin.readline().strip()
            if line == "pause":
                args.pause = True
                print("ALF: Paused...")
            line=sys.stdin.readline().strip()
            if line == "resume":
                args.pause = False
                print("ALF: Resumed...")
    except KeyboardInterrupt:
        keeprunning = False
        print("ALF: Exiting...")
    finally:
        print("ALF: Terminate Signal Received")
        for ser in serials:
            if ser.is_open:
                print(f"ALF: Closing serial port {ser.name}")
                ser.close()

if __name__ == '__main__':
    main()

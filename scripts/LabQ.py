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
from LabQLib import LABV

##########################################################################################################
############################################# LOAD CONFIG ################################################

config = {}

def load_config():
    global config
    config_file = 'config.json' 
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            print('LABQ loaded config: ', config)
    except FileNotFoundError:
        print(f"Configuration file {config_file} not found.")
    except json.JSONDecodeError:
        print(f"Configuration file {config_file} is not a valid JSON file.")

load_config()

###########################################################################################################
############################################ ARGPARSE #####################################################

parser = argparse.ArgumentParser(description="LABQ pump control V0.1")
parser.add_argument('--debug', action='store_true', help='debug mode')
parser.add_argument('--pump_head', type=int, help='pump head')
parser.add_argument('--tube_size', type=int, help='tube size')
parser.add_argument('--direction', type=str, help='direction')
parser.add_argument('--speed', type=float, help='speed')
parser.add_argument('--flow_rate', type=float, help='flow rate')
parser.add_argument('--full_speed_running', type=bool, help='full speed running')
parser.add_argument('--start_pump', action='store_true', help='start pump')
parser.add_argument('--stop_pump', action='store_true', help='stop pump')

args = parser.parse_args()

debug = args.debug
if debug:
    print(args)

def pumpcom():
    global args
    global pump
    if args.pump_head:
        pump.set_pump_head(args.pump_head)
        if debug:
            print('Pump head set')
    elif args.tube_size:
        pump.set_tube_size(args.tube_size)
        if debug:
            print('Tube size set')
    elif args.direction:
        pump.set_direction(args.direction)
        if debug:
            print('Direction set')
    elif args.speed:
        pump.set_speed(args.speed)
        if debug:
            print('Speed set')
    elif args.flow_rate:
        pump.set_flow_rate(args.flow_rate)
        if debug:
            print('Flow rate set')
    elif args.full_speed_running:
        pump.set_full_speed_running(args.full_speed_running)
        if debug:
            print('Full speed running set')
    elif args.start_pump:
        pump.start_pump()
        if debug:
            print('Pump started')
    elif args.stop_pump:
        pump.stop_pump()
        if debug:
            print('Pump stopped')

def main():
    global pump
    global args

    comport = config['LABQ_PUMP_COMPORT']
    baudrate = config['LABQ_PUMP_BAUDRATE']
    pump = LABV(port=comport, address=1, baudrate=baudrate)
    if debug:
        print('Pump: ', pump, 'Connecting')
    pump.connect()
    pumpcom()
    if debug:
        print('Pump message sent, disconnecting')
    pump.disconnect()

if __name__ == "__main__":
    main()

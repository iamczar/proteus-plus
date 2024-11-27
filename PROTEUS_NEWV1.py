from nicegui import ui
import threading
import time
import os
import pandas as pd
import subprocess
import sys
import math
import numpy as np
from datetime import datetime
from local_file_picker import local_file_picker
import csv
import json
from typing import Callable
from pathlib import Path
import shutil

###########################################################################################################
############################################# LOAD CONFIG ################################################

config = {}

def load_config():
    global config
    config_file = 'config.json' 
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            #print('Proteus loaded config: ', config)
            #print("Proteus loaded config")
    except FileNotFoundError:
        print(f"Configuration file {config_file} not found.")
    except json.JSONDecodeError:
        print(f"Configuration file {config_file} is not a valid JSON file.")


###########################################################################################################
############################################# DATA PROCESSING #############################################


def data_processing(df): 
    if df is not None:
                ###########################################################################
                ##########################  user instruction!  ############################
                ################  insert any required data processing here!  ##############
                ###########################################################################


        # Convert 'TIME' to datetime
        df['TIME'] = pd.to_datetime(df['TIME'])
        df['TIME'] = (df['TIME'] - df['TIME'].iloc[0]).dt.total_seconds() / 3600
        # PumpCal = 0.003125
        PumpCal = 0.004293
        df['Pump1_mLmin'] = (df['CIRCPUMPSPEED'])*PumpCal
        df['Pump2_mLmin'] = (df['PRESSUREPUMPSPEED'])*PumpCal

        df['Pressure_SP'] = (df['PRESSUREPID'])*(df['PRESSURESETPOINT'])
        df['Oxygen_SP'] = (df['OXYGENPID'])*(df['OXYGENSETPOINT'])

        # Calculate the rolling average over 10 data points
        df['FLOWMEASURED_rolling_avg'] = df['FLOWMEASURED'].rolling(60).mean()

        # Calculate the rolling average over 10 data points
        df['PRESSUREMEASURED_rolling_avg'] = df['PRESSUREMEASURED'].rolling(60).mean()

        # Calculate the permeate flow rate
        df['PermeateFlow'] = df['Pump1_mLmin'] - df['Pump2_mLmin']


        # df['trueflow'] =df['FLOWMEASURED']*flowcal

        OxySaturated = 200
        # Calculate the OUR
        df['OUR'] = (df['Pump2_mLmin']/1000)*(OxySaturated-df['OXYGENMEASURED2']) + (df['PermeateFlow']/1000)*(OxySaturated-df['OXYGENMEASURED2'])
        df['OUR_rollAvg_1min'] = df['OUR'].rolling(60).mean()
        df['OUR_rollAvg_5min'] = df['OUR'].rolling(300).mean()

        return


###########################################################################################################
############################################## CLASSES ####################################################
###########################################################################################################

class Module:
    def __init__(self, moduleID, seqFilename, index, data_file):
        self.moduleID = moduleID
        self.seqFilename = seqFilename
        self.index = index
        self.data_file = data_file
        self.data_frame = None
        self.num_rows = 0
        self.button = None
        self.session_label = f" Last session: None. "
        self.freeze = False
        self.subset = None
        self.data_file_row = 0
        self.len_of_datafile = count_rows(self.data_file)
        self.timewindow = {'value':{ 'min': 0.20, 'max': 0.80}}
        self.type='Circulation'

timewindow = {'value':{ 'min': 0.20, 'max': 0.80}}

class ValueContainer:
    def __init__(self, value):
        self.value = value

    def value_changed(self, new_value):
        print(f'Selected value: {new_value.value}')
        index = new_value.value
        self.value = new_value



###################################################################################################
####################################### DICTIONARIES ##############################################

index_value = ValueContainer(1)
index_list = [i for i in range(1, 24)]
tubing_list = [13,14,16,19,25]

processes = {}
modules = {}
circ_modules = []
ui_plots = {}
lem_module = None


# COLOURS
light_blue = '#D9E3F0'

############################################################################################################
################################################ FUNCTIONS #################################################



def subselect(module) -> None:  ## Subselect the data frame to get (limit) number of rows
    # print(f"Subselecting {module.moduleID} data frame")
    module.subset = None
    if module.data_frame is not None:
        if len(module.data_frame) > config['PLOT_POINTS']:
            starting_row = int(len(module.data_frame) * timewindow['value']['min'])
            finish_row = int(len(module.data_frame) * timewindow['value']['max'])
            #print(len(module.data_frame))
            #print(timewindow['value']['max'])
            #print('start and finish:')
            #print(starting_row)
            #print(finish_row)
            target_rows = finish_row - starting_row
            module.subset = module.data_frame.iloc[starting_row:finish_row:math.ceil(target_rows/(config['PLOT_POINTS']))].copy()

        else:
            # Select the last 'config['PLOT_POINTS']' number of rows
            module.subset = module.data_frame[-config['PLOT_POINTS']:].copy()
    #print(module.subset)

def module_list_update() -> None:   ## Create the modules from the serial_config file
    global moduleID
    global modules
    global circ_modules
    global lem_module
    modules = {}
    circ_modules = []
    what = config['SERIAL_CONFIG']
    with open(config['SERIAL_CONFIG'], mode='r') as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            if len(row) >= 4 and row[3]:
                moduleID = row[3]
                if int(moduleID)<config["LEM_ID_LIMIT"]:
                    data_file = os.path.join(config["DATA_FOLDER"], f'{moduleID}_data.csv')
                    module = Module(moduleID, seqFilename=None, index=1, data_file=data_file)
                    modules[moduleID] = module
                    circ_modules.append(module.moduleID)
                    load_new_rows(module)
                    subselect(module)
                    data_processing(module.subset)
                elif int(moduleID)>=config["LEM_ID_LIMIT"]:
                    moduleID = row[3]
                    data_file = os.path.join(config["DATA_FOLDER"], f'{moduleID}_data.csv')
                    module = Module(moduleID, seqFilename=None, index=1, data_file=data_file)
                    module.type = 'LEM'
                    modules[moduleID] = module
                    lem_module=module.moduleID
    #print(f"module_list_update:moduleID:{moduleID}")


def load_new_rows(module) -> None:

    if module.data_frame is None:
        start_row = 0
    else:    
        start_row = module.data_file_row
    #print(f"Loading new rows for {module.moduleID} from row {start_row}")
    
    if not os.path.exists(module.data_file):
        print(f"{module.data_file} not found. No new rows loaded.")
        return 
    
    try:
        new_rows = pd.read_csv(module.data_file, names=config['COLNAMES'], skiprows=range(0, start_row + 1), on_bad_lines='skip')
    except FileNotFoundError:
        print(f"{module.data_file} not found, creating file.")
        open(module.data_file, 'w').close()
        new_rows = pd.DataFrame(columns=config['COLNAMES'])
    
    print(new_rows)
    if not new_rows.empty:
    #    print(new_rows)
        module.data_frame = pd.concat([module.data_frame, new_rows], ignore_index=True)
        module.data_file_row = module.data_file_row + len(new_rows)
    if module.subset is not None:    
        update_line_plot()

def scan_for_modules() -> Callable[[], None]:  ## Scan for modules, this will start the module_register.py script
    def inner() -> None:
        print("Scanning for modules...")
        if processes == {}:
            process = subprocess.Popen([sys.executable, config['MODULE_REGISTER_PATH'], '-s', '-c', config['SERIAL_CONFIG']])
        else:
            print("process already running, restart Proteus to scan again")
        global modules
        modules = {}
        module_list_update()
    return inner

def null_session(target_module) -> None:   ## the 'Stop' button function, it stops the pumps and returns the valves to their 'off' state by running ALF with the null sequence
    global experiment_folder_path
    if experiment_folder_path is None:
        experiment_folder_path = os.path.join(os.getcwd(), "log")
    
    
    data_file_path = os.path.join(os.path.dirname(__file__), config["DATA_FOLDER"], f'{moduleID}_data.csv')
    #log_file_path= os.path.join(os.path.dirname(__file__), config["LOG_FOLDER"], f'{moduleID}_log.csv')
    log_file_path = os.path.join(experiment_folder_path, f'{moduleID}_log.csv')
    module_csv= os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
    if target_module in processes:
        processes[target_module].communicate(b"exit\n")
        print(f"Stopped {target_module} ALF session")
        time.sleep(1)
    alfi_session(seq_csv=config['NULLSEQUENCE'], index=17, data_csv=data_file_path, log_csv=log_file_path, module_csv=module_csv)
    print(f"Pumps stopped & valves returned to natural state.")
    time.sleep(1)
    if target_module in processes:
        processes[target_module].communicate(b"exit\n")
        print(f"Stopped {target_module} null sequence")
    else:
        print(f"No null sequence running for {target_module}")
    time.sleep(1)

def stop_experiment(target_module):
    try:
        module_csv_path = os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
        if target_module in processes:
            processes[target_module].terminate()
            print(f"-----------------------------------------Stopped {target_module} ALF session------------------------------------------------------")
            time.sleep(1)
        else:
            print(f"-----------------------------------------Target module not in process {target_module}------------------------------------------------------")

        print(f"-----------------------------------------calling run_stop_experiment ------------------------------------------------------")
        run_stop_experiment(moduleID,module_csv_path)

    except Exception as e:
        print(f"stop_experiment:ERROR: {e}")

def stop_btn_click() -> None:
    def inner():
        target_module = moduleID
        threading.Thread(target=stop_experiment(target_module), daemon=True).start()
    return inner

def start_data_logging(target_module):
    try:
        module_csv_path = os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
        if target_module in processes:
            processes[target_module].terminate()
            print(f"-----------------------------------------Stopped {target_module} ALF session------------------------------------------------------")
            time.sleep(1)
        else:
            print(f"-----------------------------------------Target module not in process {target_module}------------------------------------------------------")

        print(f"-----------------------------------------calling run_start_data_logging ------------------------------------------------------")
        run_start_data_logging(moduleID,module_csv_path)

    except Exception as e:
        print(f"stop_experiment:ERROR: {e}")
        

def start_data_logging_btn_click() -> None:
    def inner():
        target_module = moduleID
        threading.Thread(target=start_data_logging(target_module), daemon=True).start()
    return inner

def stop_data_logging(target_module):
    try:
        module_csv_path = os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
        if target_module in processes:
            processes[target_module].terminate()
            print(f"-----------------------------------------Stopped {target_module} ALF session------------------------------------------------------")
            time.sleep(1)
        else:
            print(f"-----------------------------------------Target module not in process {target_module}------------------------------------------------------")

        print(f"-----------------------------------------calling run_stop_data_logging ------------------------------------------------------")
        run_stop_data_logging(moduleID,module_csv_path)

    except Exception as e:
        print(f"stop_experiment:ERROR: {e}")

def stop_data_logging_btn_click() -> None:
    def inner():
        target_module = moduleID
        threading.Thread(target=stop_data_logging(target_module), daemon=True).start()
    return inner

def delete_all_logs(target_module):
    try:
        module_csv_path = os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])    
        run_delete_logs(moduleID,module_csv_path)
    except Exception as e:
        error_msg = f"-------------Error: retrieve_logs: ----------------- {e}"
        print(error_msg)

def confirm_delete_logs(target_module):
    with ui.dialog() as dialog:
        with ui.card():
            ui.label(f"Are you sure you want to delete all logs in module {target_module}? This action cannot be undone!")
            with ui.row().classes('justify-between'):
                ui.button("Cancel", on_click=dialog.close).props('outline')
                ui.button("Delete", on_click=lambda: [delete_all_logs(target_module), dialog.close()], color='red')
    dialog.open()

def delete_all_logs_btn_click() -> None:
    def inner():
        target_module = moduleID
        threading.Thread(target=confirm_delete_logs(target_module), daemon=True).start()
    return inner

def retrieve_logs(target_module):
    """Retrieve all files from the specified folder on the SD card."""
    def on_folder_selected(selected_folder):
        
        try:
            # Use the selected folder or fallback to the default log folder
            target_folder = selected_folder if selected_folder else os.path.join(os.getcwd(), "log")
            module_csv_path = os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
            data_file_path = os.path.join(os.path.dirname(__file__), config["DATA_FOLDER"], f'{moduleID}_data.csv')
        
            print(f"----------------------------retrieve_logs:{moduleID}-------------------------------------------------")
            print(f"----------------------------target_folder:{target_folder}----------------------------------")
            print(f"----------------------------module_csv_path:{module_csv_path}----------------------------------")
            run_retrieve_logs(moduleID,module_csv_path,target_folder,data_file_path)
            
        except Exception as e:
            error_msg = f"-------------Error: retrieve_logs: {e}"
            print(error_msg)

    # Trigger the folder picker for selecting the destination folder
    select_save_log_folder(on_folder_selected)
    
def retreive_log_btn_clicks() -> None:
    def inner():
        target_module = moduleID
        threading.Thread(target=retrieve_logs(target_module), daemon=True).start()
    return inner

def lem_stop_btn_click() -> None:
    def inner():
        global moduleID
        global lem_module
        global active_circulation_module
        active_circulation_module=moduleID
        moduleID=lem_module
        target_module = moduleID
        threading.Thread(target=null_session(target_module), daemon=True).start()
        moduleID=active_circulation_module
    return inner

def freeze_btn_click() -> None:
    def inner() -> None:
        global freeze
        freeze = not freeze
        if freeze:
            freeze_button.props('color=purple')
            freeze_button.text = "Freeze On"
        else:
            freeze_button.props('color=orange')
            freeze_button.text = "Freeze Off"
    return inner

# def start_btn_click() -> None:
#     def inner() -> None:
#         data_file_path = os.path.join(os.path.dirname(__file__), config["DATA_FOLDER"], f'{moduleID}_data.csv')
#         log_file_path= os.path.join(os.path.dirname(__file__), config["LOG_FOLDER"], f'{moduleID}_log.csv')
#         module_csv_path= os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
#         alfi_session(index=index_value.value, seq_csv=seqFilename, data_csv=data_file_path, log_csv=log_file_path, module_csv=module_csv_path)
#     return inner

experiment_folder_path = None
async def start_btn_click() -> None:
    global seqFilename

    # First, check if the sequence file has been selected
    if not seqFilename:
        # Trigger the file picker for selecting the sequence file
        await pick_seqfile()

    if seqFilename:
        # If sequence file is selected, proceed to folder selection
        def on_folder_selected(selected_folder):
            # Use the selected folder or fallback to the default log folder
            global experiment_folder_path
            experiment_folder_path = selected_folder if selected_folder else os.path.join(os.getcwd(), "log")
            
            print(f"Selected log folder: {experiment_folder_path}")
            
            # Now run the sequence using the selected log folder and selected sequence file
            data_file_path = os.path.join(os.path.dirname(__file__), config["DATA_FOLDER"], f'{moduleID}_data.csv')
            copy_data_file_to_path = os.path.join(experiment_folder_path, f'{moduleID}_data.csv')
            log_file_path = os.path.join(experiment_folder_path, f'{moduleID}_log.csv')  # Use chosen folder
            module_csv_path = os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
            
            # Copy the sequence file to the selected folder
            try:
                sequence_dest_path = os.path.join(experiment_folder_path, os.path.basename(seqFilename))
                shutil.copy(seqFilename, sequence_dest_path)
                print(f"Sequence file copied to: {sequence_dest_path}")
            except Exception as e:
                print(f"Error copying sequence file: {e}")
                
            # Call the alfi_session function with the appropriate arguments
            # print("--------------------------------start_btn_click-------------------------------------")
            # print(f"--------------------------------data_file_path:{data_file_path}-------------------------------------")
            # print(f"--------------------------------copy_data_file_to_path:{copy_data_file_to_path}-------------------------------------")
            alfi_session(index=index_value.value, seq_csv=seqFilename, data_csv=data_file_path, log_csv=log_file_path, module_csv=module_csv_path,experiment_file_path=copy_data_file_to_path)

        # Trigger the folder picker after sequence file selection
        select_save_log_folder(on_folder_selected)
    else:
        print("Sequence file not selected, cannot start sequence.")

def mass_start_btn_click() -> None:
    def inner() -> None:
        print(f"Starting mass balance session") 
        processes['mass_balance'] = subprocess.Popen([sys.executable, config['MASS_BALANCE_PATH']])
    return inner

def mass_stop_btn_click() -> None:
    def inner() -> None:
        if 'mass_balance' in processes:
            processes['mass_balance'].communicate(b"exit\n")
            print(f"Stopped mass balance session")
    return inner

def purge_btn_click() -> None:
    def inner() -> None:
        for plot in plot_dict.values():
            ui_plots[plot['name']].clear()
        for module in modules.values():
            module.data_frame = None
            module.data_file_row = 0
    return inner

async def open_new_experiment_dialog() -> None:
    with ui.dialog() as dialog:
        with ui.card():
            ui.label('Enter experiment name:')
            folder_name_input = ui.input(label='Folder Name', placeholder='Enter folder name...')
    
            with ui.row():
                # OK button to create the folder
                ui.button('OK', on_click=lambda: create_experiment_folder(dialog, folder_name_input.value))
                # Cancel button to close the dialog without doing anything
                ui.button('Cancel', on_click=dialog.close)

    dialog.open()  # Explicitly open the dialog after defining it


async def create_experiment_folder(dialog, folder_name: str) -> None:
    if folder_name:
        # Construct the path to the 'experiments' directory
        experiment_folder_path = os.path.join(os.getcwd(), "experiments", folder_name)
        try:
            os.makedirs(experiment_folder_path, exist_ok=True)  # Create the folder
            print(f"Folder '{folder_name}' created at {experiment_folder_path}.")
        except Exception as e:
            print(f"Error creating folder '{folder_name}': {e}")
    else:
        print("Error: Folder name cannot be empty.")
    
    dialog.close()  # Close the dialog once folder creation process is done
    
seqFilename = None  # Initialize the global variable to store the sequence file
def select_save_log_folder(callback, start_directory: str = os.getcwd()) -> None:
    """Custom folder picker to select a directory to save logs."""

    current_directory = Path(start_directory).expanduser()

    def update_file_grid():
        """Updates the UI grid to show the contents of the current directory."""
        folder_contents = list(current_directory.glob('*'))
        folder_contents.sort(key=lambda p: (not p.is_dir(), p.name.lower()))

        file_grid.options['rowData'] = [{
            'name': f'📁 {p.name}' if p.is_dir() else p.name,
            'path': str(p),
        } for p in folder_contents]

        if current_directory != current_directory.parent:
            # Add parent directory navigation (without <strong> tags)
            file_grid.options['rowData'].insert(0, {
                'name': '📁 ..',  # Display as a simple text for the parent folder
                'path': str(current_directory.parent),
            })

        file_grid.update()

    def handle_double_click(e):
        """Handles folder navigation via double-click."""
        nonlocal current_directory
        selected_path = Path(e.args['data']['path'])
        if selected_path.is_dir():
            current_directory = selected_path
            update_file_grid()

    def handle_select():
        """Handles the selection of the current folder."""
        callback(str(current_directory))
        folder_dialog.close()

    # Create the dialog to display folder contents
    with ui.dialog() as folder_dialog, ui.card():
        ui.label(f'Select Folder (current: {current_directory})')

        file_grid = ui.aggrid({
            'columnDefs': [{'field': 'name', 'headerName': 'File'}],
            'rowSelection': 'single',
        }).on('cellDoubleClicked', handle_double_click)

        with ui.row().classes('w-full justify-end'):
            ui.button('Cancel', on_click=folder_dialog.close).props('outline')
            ui.button('Select', on_click=handle_select)

    update_file_grid()  # Load the initial directory contents
    folder_dialog.open()  # Open the dialog


def labq_session(debug=False, pump_head=None, tube_size=None, direction=None, speed=None, flow_rate=None, full_speed_running=False, start_pump=False, stop_pump=False) -> None:  
    if 'labq' in processes:
        if processes['labq'].poll() is None:
            print("LabQ script already running.")
            return     
    cmd_args = [config['LABQ_FILEPATH']]
    if debug:
        cmd_args.append('--debug')
    if pump_head:
        cmd_args.extend(['--pump_head', str(pump_head)])
    if tube_size:
        cmd_args.extend(['--tube_size', str(tube_size)])
    if direction:
        cmd_args.extend(['--direction', str(direction)])
    if speed:
        cmd_args.extend(['--speed', str(speed)])
    if flow_rate:
        cmd_args.extend(['--flow_rate', str(flow_rate)])
    if full_speed_running:
        cmd_args.append('--full_speed_running')
    if start_pump:
        cmd_args.append('--start_pump')
    if stop_pump:
        cmd_args.append('--stop_pump')

    print(cmd_args)
    processes['labq'] = subprocess.Popen([sys.executable] + cmd_args, stdin=subprocess.PIPE)
    print(f"LabQ script started.")
    
def run_retrieve_logs(module_id,serial_conf,target_folder,data_folder):
    if moduleID in processes:
        if processes[module_id].poll() is None:
            print(f"ALFI script already running for {moduleID}, poll: {processes[moduleID].poll()}")
            return
    cmd_args = ['scripts\\retrieve_sessions_logs.py','-u', str(moduleID)]
    cmd_args.extend(['-s', serial_conf])
    cmd_args.extend(['-t', target_folder])
    cmd_args.extend(['-d', data_folder])
    processes[moduleID] = subprocess.Popen([sys.executable] + cmd_args, stdin=subprocess.PIPE)
    
def run_stop_experiment(module_id,serial_conf):    
    if moduleID in processes:
        if processes[module_id].poll() is None:
            print(f"ALFI script already running for {moduleID}, poll: {processes[moduleID].poll()}")
            return
    cmd_args = ['scripts\\SEND_STOP.py','-u', str(moduleID)]
    cmd_args.extend(['-s', serial_conf])
    processes[moduleID] = subprocess.Popen([sys.executable] + cmd_args, stdin=subprocess.PIPE)

def run_delete_logs(module_id,serial_conf):
    if moduleID in processes:
        if processes[module_id].poll() is None:
            print(f"ALFI script already running for {moduleID}, poll: {processes[moduleID].poll()}")
            return
    cmd_args = ['scripts\\delete_module_logs.py','-u', str(moduleID)]
    cmd_args.extend(['-s', serial_conf])
    processes[moduleID] = subprocess.Popen([sys.executable] + cmd_args, stdin=subprocess.PIPE)

def run_stop_data_logging(module_id,serial_conf):
    if moduleID in processes:
        if processes[module_id].poll() is None:
            print(f"ALFI script already running for {moduleID}, poll: {processes[moduleID].poll()}")
            return
    cmd_args = ['scripts\\SEND_STOP_DATA_LOGGING.py','-u', str(moduleID)]
    cmd_args.extend(['-s', serial_conf])
    processes[moduleID] = subprocess.Popen([sys.executable] + cmd_args, stdin=subprocess.PIPE)
    
def run_start_data_logging(module_id,serial_conf):
    if moduleID in processes:
        if processes[module_id].poll() is None:
            print(f"ALFI script already running for {moduleID}, poll: {processes[moduleID].poll()}")
            return
    cmd_args = ['scripts\\SEND_START_DATA_LOGGING.py','-u', str(moduleID)]
    cmd_args.extend(['-s', serial_conf])
    processes[moduleID] = subprocess.Popen([sys.executable] + cmd_args, stdin=subprocess.PIPE)
    
def alfi_session(debug=False, seq_csv=None, log_csv=None, baud=None, pause=False, module_csv=None, data_csv=None, index=None, serial_config=None, port=None,experiment_file_path = None) -> None:
    global experiment_folder_path  # Access the experiment folder path
    
    # Ensure we have a valid experiment folder, fallback to default log folder if not created
    if experiment_folder_path is None:
        experiment_folder_path = os.path.join(os.getcwd(), "log")

    # Define the log file path within the experiment folder
    log_file_path = os.path.join(experiment_folder_path, f'{moduleID}_log.csv')
    
    # See ALF.py for the command line arguments
    if moduleID in processes:
        if processes[moduleID].poll() is None:
            print(f"ALFI script already running for {moduleID}, poll: {processes[moduleID].poll()}")
            return
    
    cmd_args = [config['ALF_FILEPATH'] , '-u', str(moduleID)]
    if debug:
        cmd_args.append('--debug')
    if seq_csv:
        cmd_args.extend(['-q', seq_csv])
    if log_csv:
        cmd_args.extend(['-l', log_file_path])
    if baud:
        cmd_args.extend(['-b', str(baud)])
    if pause:
        cmd_args.append('-p')
    if module_csv:
        cmd_args.extend(['-m', module_csv])
    if data_csv:
        cmd_args.extend(['-d', data_csv])
    if index is not None:
        cmd_args.extend(['-i', str(index)])
    if serial_config:
        cmd_args.extend(['-s', serial_config])
    if port:
        cmd_args.extend(['-c', port])
    if freeze:
        cmd_args.append('-p')
    if experiment_file_path:
        cmd_args.extend(['-e', experiment_file_path])
    # print("-------------------------------------------------------cmd_args--------------------------------------------------------")
    # print(cmd_args)
    processes[moduleID] = subprocess.Popen([sys.executable] + cmd_args, stdin=subprocess.PIPE)
    module = modules[moduleID]
    module.seqFilename = seq_csv
    module.index = index
    module.freeze = freeze
    module.session_label = f"Sequence: {module.seqFilename}, Index = {module.index}, Freeze = {module.freeze}"
    print(f"ALFI started sequence file for {moduleID}, index = {module.index}, seqFilename = {module.seqFilename}")
    session_label.text = module.session_label
    print('updated session label for module ', moduleID, ' to ', module.session_label)

def count_rows(csv_file):
    i = 0
    abs_path = os.path.abspath(csv_file)  # Get the absolute path
    # print(f"Attempting to open file at: {abs_path}")  # Print the absolute path
    if not os.path.exists(csv_file):  # Check if the file exists
        print(f"File {abs_path} not found, returning 0.")
        return i  # Return 0 if the file does not exist
    with open(csv_file, 'r') as f:
        for i, _ in enumerate(f, 1):
            pass
    return i

def refresh_all() -> None:
    for module in modules.values():
        if module.type == 'Circulation':
            color = 'blue' if moduleID == module.moduleID else 'lightblue'
            module.button.props(f'color={color}')
    module = modules[moduleID]
    module.len_of_datafile= count_rows(module.data_file)
    if module.len_of_datafile > module.data_file_row:
        load_new_rows(module)
        module.data_file_row = module.len_of_datafile
        print(f"Data file updated for module {moduleID}, data file row = {module.data_file_row}")
    subselect(module)
    data_processing(module.subset)
    update_line_plot()
    #print('Running Processes: ',processes)
    for process in list(processes.keys()):
        if processes[process].poll() is None:
            print(f"Process {process} is still running.")
        else:
            print(f"Process {process} has terminated.")
            del processes[process]

def update_line_plot() -> None:
    module = modules[moduleID]
    for plot in plot_dict.values():
        # Check if module.subset is not None and has length greater than 0
        if module.subset is not None and len(module.subset) > 0:
            y_values = [module.subset[y].values for y in plot['y_values']]
            x_values = module.subset['TIME'].values  # 'TIME' is already datetime 
            ui_plots[plot['name']].clear()
            ui_plots[plot['name']].push(x_values, y_values)
            # print(f"Updating plot {plot['name']} for module {moduleID}, x_values = {x_values}, y_values = {y_values}")


def select_mod_id(value) -> Callable[[], None]: # Used to select the active module by mod ID.
    def inner() -> None:
        global moduleID
        moduleID = value
        print(f"Module ID selected: {moduleID}")
        session_label.text = modules[moduleID].session_label
        update_line_plot()
    return inner

async def pick_seqfile() -> None: # uses local_file_picker to select files for sequences
    global seqFilename
    result = await local_file_picker(cwd, multiple=True)        
    seqFilename = result[0] if result else ""
    sequence_button.text = f"Sequence: {os.path.basename(seqFilename)}" if seqFilename else ""
    print(f"Selected file: {seqFilename}")

def pump_calibration() -> Callable[[], None]: # Used to calibrate the pumps
    def inner() -> None:
        print("Pump calibration")
    return inner

def build_lem_seq(media, circ_module, volume) -> None: # Used to build the LEM sequence
    df = pd.read_csv(config['LEM_SEQ_PATH'])
    print(df)
    df.at[1, 'dispenseVolumeSP'] = volume
    for col in df.columns:
        if col.startswith('valve'):
            if not col.endswith('Pin'):
                df.at[1, col] = 0
    #find the media in the list of media,
    # print(config['MEDIA_LIST'])
    # print(media)
    # print(circ_modules)
    # print(circ_module)
    media_index = config['MEDIA_LIST'].index(media)
    #find the module in the list of modules
    module_index = circ_modules.index(circ_module)
    valve_to_open = (4 * module_index) + media_index + 1
    df.at[1, f'valve{valve_to_open}'] = 1
    df.at[1, 'dispensePara']= module_index+1
    print(df)
    df.to_csv(config['LEM_SEQ_PATH'], index=False)

def lem_dispense(media,circ_module) -> Callable[[], None]: # Used to dispense LEM
    def inner() -> None:
        print(module)
        global lem_module
        global moduleID
        global lem_volume_input
        if lem_module in processes:
            processes[lem_module].communicate(b"exit\n")
            print(f"Stopped {lem_module} ALF session")
            time.sleep(1)
            for process in list(processes.keys()):
                if processes[process].poll() is None:
                    print(f"Process {process} is still running.")
                else:
                    print(f"Process {process} has terminated.")
                    del processes[process]
        print(f"Dispensing {media} in {circ_module}")
        build_lem_seq(media,circ_module,lem_volume_input.value)
        if not lem_module in processes:
            active_circulation_module=moduleID
            moduleID=lem_module
            # print(f"Dispensing {lem}")
            module_csv_path= os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
            alfi_session(seq_csv=config['LEM_SEQ_PATH'], module_csv=module_csv_path)
            moduleID=active_circulation_module
    return inner


############################################################################################################
##########################################  SETUP AND RUN  #################################################

freeze = False

cwd = os.getcwd()
if os.getcwd()!=os.path.abspath(__file__):
    #print("Current Working Directory: ", os.getcwd())
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    #print("New Working Directory: ", os.getcwd())

load_config()

module_list_update()

try:
    with open(config['PLOT_DICT'], 'r') as f:
        plot_dict = json.load(f)
except FileNotFoundError:
    print("Error: The file 'plot_dict.json' was not found.")
except json.JSONDecodeError:
    print("Error: The file 'plot_dict.json' does not contain valid JSON.")
for key, value in plot_dict.items():
    print(key,": ", value)

############################################################################################################
################################################ UI ########################################################

ui.page_title('PROTEUS')

with ui.header(elevated=True).style('background-color: #697689').classes('items-left justify-between h-12.5'):
    with ui.row().classes('w-full'):
        for module in modules.values():
            if module.type == 'Circulation':
                module.button = ui.button(module.moduleID, on_click=select_mod_id(module.moduleID), color=light_blue)
        
with ui.footer(fixed=True).style('background-color: #a9b1be').props('width=100'):
    with ui.row().classes('w-full'):
        with ui.tabs() as tabs:
            tab_graphs = ui.tab('g', label = 'Module Control')
            tab_lem = ui.tab('l', label = 'LEM')
            tab_LabQ = ui.tab('q', label = 'LabQ')
            tab_advanced = ui.tab('p', label = 'ADVANCED CONTROLS')
            tab_image = ui.tab('i', label='PI&D')


with ui.tab_panels(tabs, value=tab_graphs).classes('w-full'):
    with ui.tab_panel(tab_graphs): 
        with ui.grid(columns=1).classes('items-start'):       
            with ui.grid(columns=5).classes('items-start'):
                new_experiment=ui.button("New Experiment", on_click=open_new_experiment_dialog, color='blue')
                sequence_button=ui.button('Select sequence', on_click=pick_seqfile)
                start_button=ui.button("Begin Sequence", on_click=start_btn_click, color='green')  
                stop_button = ui.button("STOP", on_click=stop_btn_click(), color='red')
                ui.space()
                start_data_logging_button = ui.button("Start Data Logging", on_click=start_data_logging_btn_click(), color='green')
                stop_data_logging_button = ui.button("Stop Data Logging", on_click=stop_data_logging_btn_click(), color='red') 
                retreive_logs_button = ui.button("Retrive Logs", on_click=retreive_log_btn_clicks(), color='red')
                delete_all_logs_button = ui.button("Delete All Logs", on_click=delete_all_logs_btn_click(), color='red')
                ui.space()
                ui.space()
                index_dropdown = ui.select(label='Select Index', options=index_list).bind_value_to(index_value, "value")
                freeze_button=ui.button("Index Freeze Off", on_click=freeze_btn_click(), color='orange')
                session_label = ui.label('')
                ui.space()
                ui.space()
            with ui.grid(columns=1).classes('items-start'):
                ui.label(text='Set Time Window')
                module = modules[moduleID]
                # slider = ui.slider(min=0, max=1, step=0.01, value=0).bind_value_to(module.timewindow, 'value')
                min_max_range = ui.range(min=0, max=1, step=0.01, value={'min': 0.00, 'max': 1.00}).bind_value_to(timewindow).on('mouseup',(refresh_all))
                # ui.label().bind_text_from(min_max_range, 'value',
                #           backward=lambda v: f'min: {v["min"]}, max: {v["max"]}')

            with ui.grid(columns=3).classes('items-start'):
                for plot in plot_dict.values():
                    line_plot = ui.line_plot(n=plot['number_of_lines'], limit=config['PLOT_POINTS'] ) \
                        .with_legend(plot['legend'])
                    ax = line_plot.fig.gca()  # Get the current Axes instance on the current figure
                    ax.set_xlabel('Time (hours)')
                    ax.set_ylabel(plot['y_label'])
                    ax.set_title(plot['title'])
                    # if 'y_limits' in plot:
                    #     ax.set_ylim(plot['y_limits'])  # Correctly set y-axis limits here
                    ui_plots[plot['name']] = line_plot

    with ui.tab_panel(tab_advanced):
        ui.button('Scan for Modules', on_click=scan_for_modules())
        ui.button('Calibrate Pump', on_click=pump_calibration())
        ui.button('RELOAD DATA', on_click=purge_btn_click(), color='red')
        ui.button('Start Mass Balance', on_click=mass_start_btn_click())
        ui.button('Stop Mass Balance', on_click=mass_stop_btn_click())

    with ui.tab_panel(tab_lem):
        media_list=config['MEDIA_LIST']

        with ui.grid(columns=5):
            ui.space()
            lem_volume_input=ui.number(label='Volume (mL)', value=2, format='%.2f')
            ui.space()
            lem_stop_btn=ui.button('LEM STOP', on_click=lem_stop_btn_click, color='RED')
            ui.space()
        
        with ui.grid(columns=len(modules)):
            ui.space()
            for module in circ_modules:
                ui.label(module)
            for i in range(0,4):
                ui.label(media_list[i])
                for module in circ_modules:
                    ui.button(f'DISPENSE', on_click=lem_dispense(media_list[i],module), color=light_blue)

    with ui.tab_panel(tab_LabQ):
        with ui.grid(columns=4).classes('items-start'):
            labq_start = ui.button("Start Pump", on_click=lambda: labq_session(start_pump=True), color='green')
            labq_stop = ui.button("Stop Pump", on_click=lambda: labq_session(stop_pump=True), color='red')
            ui.space()
            labq_full_speed = ui.button("Full Speed Running", on_click=lambda: labq_session(full_speed_running=True), color='red')
            labq_direction = ui.button("Pump Clockwise", on_click=lambda: labq_session(direction=1), color='orange')
            labq_direction = ui.button("Pump Counter-Clockwise", on_click=lambda: labq_session(direction=0), color='orange')
            ui.space()
            ui.space()
            ui.space()
            ui.space()
            ui.space()
            ui.space()
            labq_speed = ui.number(label='Speed (RPM)', value=0, format='%.2f')
            labq_session_btn = ui.button("Confirm", on_click=lambda: labq_session(speed=labq_speed.value), color='orange')
            ui.space()
            ui.space()
            labq_flow_rate = ui.number(label='Flow Rate (mL/min)', value=0, format='%.2f')
            labq_session_btn = ui.button("Confirm", on_click=lambda: labq_session(flow_rate=labq_flow_rate.value), color='orange')
            ui.space()
            ui.space()
            labq_tubing = ui.select(label='Select Tubing', options=tubing_list)
            labq_session_btn = ui.button("Confirm", on_click=lambda: labq_session(tube_size=labq_tubing.value), color='orange')
            ui.space()

    # New Image tab panel
    with ui.tab_panel(tab_image):
        ui.image('resource/PI&DImage.png').style('width: 100%; height: auto; display: block; margin: 0 auto;')

line_updates = ui.timer(5, refresh_all)

for module in modules.values():
    if module.type == 'Circulation':
        select_mod_id(module.moduleID)()

ui.run(port=5500)

from nicegui import ui, app
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
import numpy as np
import plotly.graph_objects as go
from plotly_resampler import FigureResampler #requires 'pip install psutil
import signal
import sys
import psutil  # Requires `pip install psutil`

from tabs.software_update_tab import load_software_update_tab


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
        #df['TIME'] = (df['TIME'] - df['TIME'].iloc[0]).dt.total_seconds() / 3600
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
seqFilename = None  # Initialize the global variable to store the sequence file
processes = {}
modules = {}
circ_modules = []
ui_plots = {}
lem_module = None
experiment_folder_path = None
paused = False  

# COLOURS
light_blue = '#D9E3F0'

    # 🔹 Column mapping based on Proteus structure
COLUMN_MAPPING = {
    0: 'TIME', 1: 'NULLLEADER', 2: 'MODUID', 3: 'COMMAND', 4: 'STATEID',
    5: 'OXYMEASURED', 6: 'PRESSUREMEASURED', 7: 'FLOWMEASURED', 8: 'TEMPMEASURED',
    9: 'CIRCPUMPSPEED', 10: 'PRESSUREPUMPSPEED', 11: 'PRESSUREPID', 12: 'PRESSURESETPOINT',
    13: 'PRESSUREKP', 14: 'PRESSUREKI', 15: 'PRESSUREKD', 16: 'OXYGENPID',
    17: 'OXYGENSETPOINT', 18: 'OXYGENKP', 19: 'OXYGENKI', 20: 'OXYGENKD',
    21: 'OXYGENMEASURED1', 22: 'OXYGENMEASURED2', 23: 'OXYGENMEASURED3',
    24: 'OXYGENMEASURED4', 25: 'NULLTRAILER'
}


############################################################################################################
################################################ FUNCTIONS #################################################

def subselect(module) -> None:  ## Subselect the data frame to get (limit) number of rows
    """Always selects the last 10,000 rows from module.data_frame for plotting.
    If there are fewer than 10,000 rows, it displays all available data."""
    if module.data_frame is not None:
        # Always take the last 10,000 rows or fewer if not available
        module.subset = module.data_frame.iloc[-10_000:].copy()

def module_list_update() -> None:   ## Create the modules from the serial_config file
    global moduleID
    global modules
    global circ_modules
    global lem_module
    modules = {}
    circ_modules = []
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


def load_new_rows(module) -> None:
    if module.data_frame is None:
        start_row = 0
    else:    
        start_row = module.data_file_row

    if not os.path.exists(module.data_file):
        print(f"❌ {module.data_file} not found. No new rows loaded.")
        return 
    
    new_rows = pd.read_csv(module.data_file, names=config['COLNAMES'], skiprows=range(0, start_row + 1), on_bad_lines='skip')

    if not new_rows.empty:
        module.data_frame = pd.concat([module.data_frame, new_rows], ignore_index=True)
        module.data_file_row += len(new_rows)

def scan_for_modules() -> Callable[[], None]:  ## Scan for modules, this will start the module_register.py script
    def inner() -> None:
        log.push("Scanning for modules...")
        if processes == {}:
            process = subprocess.Popen([sys.executable, config['MODULE_REGISTER_PATH'], '-s', '-c', config['SERIAL_CONFIG']])
        else:
            log.push("process already running, restart Proteus to scan again")
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
            log.push(f"---------------------Stopped {target_module} ALF session------------------------------------------------------")
            time.sleep(1)
        else:
            log.push(f"---------------------Target module not in process {target_module}------------------------------------------------------")

        log.push(    f"---------------------calling run_stop_experiment ------------------------------------------------------")
        run_stop_experiment(moduleID,module_csv_path)

    except Exception as e:
        print(f"stop_experiment:ERROR: {e}")

def stop_btn_click() -> None:
    def inner():
        target_module = moduleID
        threading.Thread(target=stop_experiment(target_module), daemon=True).start()
    return inner       

async def start_data_logging_btn_click() -> None:
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
                            
            run_start_data_logging(index=index_value.value, 
                                    seq_csv=seqFilename, 
                                    data_csv=data_file_path, 
                                    log_csv=log_file_path, 
                                    module_csv=module_csv_path,
                                    experiment_file_path=copy_data_file_to_path)

        # Trigger the folder picker after sequence file selection
        select_save_log_folder(on_folder_selected)
    else:
        print("Sequence file not selected, cannot start sequence.")

def stop_data_logging(target_module):
    try:
        module_csv_path = os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
        if target_module in processes:
            processes[target_module].terminate()
            print(f"---------------------Stopped {target_module} ALF session------------------------------------------------------")
            time.sleep(1)
        else:
            print(f"---------------------Target module not in process {target_module}------------------------------------------------------")

        print(    f"---------------------calling run_stop_data_logging ------------------------------------------------------")
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
                
            alfi_session(index=index_value.value, 
                         seq_csv=seqFilename, 
                         data_csv=data_file_path, 
                         log_csv=log_file_path, 
                         module_csv=module_csv_path,
                         experiment_file_path=copy_data_file_to_path)

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
            folder_name_input = ui.input(label='[experiment]', value=datetime.now().strftime('%d_%b_%Y'), placeholder=datetime.now().strftime('%d_%b_%Y'))
    
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
        experiment_file.set_text("Experiment filed in :" + experiment_folder_path)
        try:
            os.makedirs(experiment_folder_path, exist_ok=True)  # Create the folder
            print(f"Folder '{folder_name}' created at {experiment_folder_path}.")
        except Exception as e:
            print(f"Error creating folder '{folder_name}': {e}")
    else:
        print("Error: Folder name cannot be empty.")
    
    dialog.close()  # Close the dialog once folder creation process is done
    
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
    
def run_start_data_logging(debug=False, 
                            seq_csv=None, 
                            log_csv=None, 
                            baud=None, 
                            pause=False, 
                            module_csv=None, 
                            data_csv=None, 
                            index=None, 
                            serial_config=None,
                            port=None,
                            experiment_file_path = None):
    global seqFilename

    # Stop existing processes first just in case an existing alfi is running
    # module_csv_path = os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
    
    if moduleID in processes:
        processes[moduleID].terminate()
        print(f"Stopped {moduleID} ALF session")
        time.sleep(1)
        
    global experiment_folder_path  # Access the experiment folder path
    
    # Ensure we have a valid experiment folder, fallback to default log folder if not created
    if experiment_folder_path is None:
        experiment_folder_path = os.path.join(os.getcwd(), "log")

    # Define the log file path within the experiment folder
    log_file_path = os.path.join(experiment_folder_path, f'{moduleID}_log.csv')

    cmd_args = ['scripts\\SEND_START_DATA_LOGGING.py','-u', str(moduleID)]
    
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
    
def alfi_session(debug=False, 
                 seq_csv=None, 
                 log_csv=None, 
                 baud=None, 
                 pause=False, 
                 module_csv=None, 
                 data_csv=None, 
                 index=None, 
                 serial_config=None,
                 port=None,
                 experiment_file_path = None) -> None:
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

def toggle_pause():# ✅ Add button to toggle graph updates
    global paused
    paused = not paused  # Flip pause state

    # ✅ Update button text and color dynamically
    if paused:
        pause_button.text = "Resume Graphs"
        pause_button.props('color=orange')
        print("⏸ Graph updates paused.")
    else:
        pause_button.text = "Pause Graphs"
        pause_button.props('color=green')
        print("▶️ Graph updates resumed.")

def refresh_all() -> None:# ✅ Track whether updates are paused
    global paused

    if paused:
        print("⏸ Graph updates paused.")
        return  # ✅ Stop refreshing if paused
    
    for module in modules.values():
        if module.type == 'Circulation':
            color = 'blue' if moduleID == module.moduleID else 'lightblue'
            module.button.props(f'color={color}')
    module = modules[moduleID]
    module.len_of_datafile= count_rows(module.data_file)
    if module.len_of_datafile > module.data_file_row:
        load_new_rows(module)
        module.data_file_row = module.len_of_datafile
        #print(f"Data file updated for module {moduleID}, data file row = {module.data_file_row}")
    subselect(module)
    data_processing(module.subset)
    update_line_plot()
    for url in app.urls:
        if '192' in url:
            LAN_ID=url
    url_tag.set_text('available on the internal LAN on '+LAN_ID)
    
    for process in list(processes.keys()):
        if processes[process].poll() is None:
            print(f"Process {process} is still running.")
        else:
            print(f"Process {process} has terminated.")
            del processes[process]

def update_line_plot() -> None:
    module = modules.get(moduleID)
        
    if module is None or module.subset is None or module.subset.empty:
        print(f"❌ ERROR: No data in module.subset for module {moduleID}")
        return  # Stop execution if there's no data

    # print("🖼️ Updating UI plots...")  # Debugging log

    # Clear existing UI elements to prevent duplication
    module_control_graph_.clear()

    with module_control_graph_:
        with ui.grid(columns=3).classes('items-start'):  # ✅ Display plots in 3 columns
            for plot in plot_dict.values():
                # print(f"📊 Plotting: {plot['name']}")  # Debugging log

                # Extract x and y values
                x_values = module.subset['TIME'].values if 'TIME' in module.subset else module.subset.index.values
                y_values = [module.subset[y].values for y in plot['y_values'] if y in module.subset]

                # Debugging: Check data size
                # print(f"📈 Data Size: {len(x_values)} samples")

                # Limit to last 10,000 samples
                max_samples = 10_000
                if len(x_values) > max_samples:
                    x_values = x_values[-max_samples:]
                    y_values = [y[-max_samples:] for y in y_values]

                # Handle empty data
                if len(x_values) == 0 or all(len(y) == 0 for y in y_values):
                    print(f"⚠️ WARNING: Empty x_values or y_values for {plot['name']}")
                    continue

                # Check if the figure already exists
                if plot['name'] in ui_plots:
                    fig = ui_plots[plot['name']]
                    fig.data = []  # Clear old traces

                    for i, y in enumerate(y_values):
                        fig.add_trace(go.Scatter(x=x_values, y=y, mode='lines', name=plot['y_values'][i]))

                    fig.update_layout(
                        width=600, height=500,
                        xaxis_title="Time (Absolute)",
                        yaxis_title=plot['y_label'],
                        title=plot['title'],
                        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
                        margin=dict(l=20, r=20, t=25, b=20),
                    )
                else:
                    # Create a new figure if it doesn't exist
                    fig = FigureResampler(go.Figure())

                    for i, y in enumerate(y_values):
                        fig.add_trace(go.Scatter(x=x_values, y=y, mode='lines', name=plot['y_values'][i]))

                    fig.update_layout(
                        width=600, height=500,
                        xaxis_title="Time (Absolute)",
                        yaxis_title=plot['y_label'],
                        title=plot['title'],
                        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
                        margin=dict(l=20, r=20, t=25, b=20),
                    )

                    # Store in dictionary and render in UI
                    ui_plots[plot['name']] = fig

                # ✅ Display in UI within the 3-column layout
                ui.plotly(fig)
    message= "graphs updated at: "+datetime.now().strftime('%d/%b/%Y %X:%p  ')  #datestamp , slicing off last 7 characters
    log.push (message)
    
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

def process_data(dfh): # 🔹 Data Processing Function
    if dfh is None or dfh.empty:
        print("Error: DataFrame is empty or invalid.")
        return None

    dfh['TIME'] = pd.to_datetime(dfh['TIME'], errors='coerce')
    dfh = dfh.dropna(subset=['TIME'])  # Remove invalid timestamps

    # Pump Calibration
    pump_cal = 0.004293
    dfh['Pump1_mLmin'] = dfh['CIRCPUMPSPEED'] * pump_cal
    dfh['Pump2_mLmin'] = dfh['PRESSUREPUMPSPEED'] * pump_cal

    # Set Points
    dfh['Pressure_SP'] = dfh['PRESSUREPID'] * dfh['PRESSURESETPOINT']
    dfh['Oxygen_SP'] = dfh['OXYGENPID'] * dfh['OXYGENSETPOINT']

    # Rolling Averages
    dfh['FLOWMEASURED_rolling_avg'] = dfh['FLOWMEASURED'].rolling(60).mean()
    dfh['PRESSUREMEASURED_rolling_avg'] = dfh['PRESSUREMEASURED'].rolling(60).mean()

    # Permeate Flow
    dfh['PermeateFlow'] = dfh['Pump1_mLmin'] - dfh['Pump2_mLmin']

    # Oxygen Uptake Rate (OUR)
    oxy_saturated = 200
    dfh['OUR'] = ((dfh['Pump2_mLmin'] / 1000) * (oxy_saturated - dfh['OXYGENMEASURED2']) +
                (dfh['PermeateFlow'] / 1000) * (oxy_saturated - dfh['OXYGENMEASURED2']))
    dfh['OUR_rollAvg_1min'] = dfh['OUR'].rolling(60).mean()
    dfh['OUR_rollAvg_5min'] = dfh['OUR'].rolling(300).mean()

    return dfh

async def pick_data_file():# 🔹 File Picker Function
    result = await local_file_picker(os.path.dirname(__file__), multiple=False)
    if result:
        selected_file_path['path'] = result[0]
        selected_file_label.text = f"Selected file: {os.path.basename(selected_file_path['path'])}"
        print(f"Selected file: {selected_file_path['path']}")
    else:
        selected_file_label.text = "No file selected."

def load_csv_in_chunks(filepath, chunk_size=50000):# 🔹 Optimized Data Loading with Chunking
    chunks = []
    for chunk in pd.read_csv(filepath, on_bad_lines='warn', header=None, low_memory=False, chunksize=chunk_size):
        chunk.rename(columns=COLUMN_MAPPING, inplace=True)
        chunk['TIME'] = pd.to_datetime(chunk['TIME'], errors='coerce')
        chunk.dropna(subset=['TIME'], inplace=True)
        chunks.append(chunk)
    
    return pd.concat(chunks, ignore_index=True)

async def load_and_plot_data():# 🔹 Load and Plot Data with Optimization
    if not selected_file_path['path']:
        print("No file selected.")
        return

    print("Loading and Plotting Data...")
    try:
        dfh = load_csv_in_chunks(selected_file_path['path'])
        
        # Convert numeric columns
        numeric_cols = [col for col in COLUMN_MAPPING.values() if col not in ['TIME', 'NULLLEADER']]
        dfh[numeric_cols] = dfh[numeric_cols].apply(pd.to_numeric, errors='coerce').fillna(0)

        # Process Data
        dfh = process_data(dfh)

        # Load plot configuration
        try:
            with open(config['PLOT_DICT'], 'r') as f:
                history_plot_dict = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print("Error: Invalid or missing 'plot_dict.json'.")
            return

        # Clear previous graphs
        graph_area.clear()

        # 🔹 Generate and Render Plots with `plotly-resampler`
        with graph_area:
            with ui.grid(columns=3).classes('items-start'):
                for plot in history_plot_dict.values():
                    traces = []

                    for y in plot['y_values']:
                        if y in dfh.columns:
                            x_values = dfh['TIME'].values
                            y_values = dfh[y].values
                            new_trace = go.Scatter(
                                x=x_values,
                                y=y_values,
                                mode='lines',
                                name=y
                            )
                            traces.append(new_trace)

                    fig = FigureResampler(go.Figure())
                    for trace in traces:
                        fig.add_trace(trace, max_n_samples=5000)  # Limit displayed points dynamically

                    fig.update_layout(
                        width=600, height=500,
                        xaxis_title="Time (Absolute)",
                        yaxis_title=plot['y_label'],
                        title=plot['title'],
                        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
                        margin=dict(l=20, r=20, t=25, b=20),
                    )

                    # Add the resampled Plotly figure to NiceGUI
                    ui.plotly(fig)

    except Exception as e:
        print(f"Error loading or plotting data: {e}")






def shutdown_app():
    """Stops all Python processes related to Proteus and exits the UI safely."""
    print("⚠️ Shutting down Proteus...")

    # ✅ Kill Proteus-related processes
    current_pid = os.getpid()  # Get the current script's PID
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] == 'python.exe' or proc.info['name'] == 'python3':  # Match Python processes
                if proc.info['pid'] != current_pid:  # Avoid killing the current process
                    print(f"💀 Killing process {proc.info['pid']}: {' '.join(proc.info['cmdline'])}")
                    proc.terminate()  # Graceful shutdown
                    time.sleep(1)
                    if proc.is_running():
                        proc.kill()  # Force kill if still running
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    # ✅ Shutdown NiceGUI properly
    print("💥 Exiting Proteus UI...")
    os._exit(0)  # Immediate termination of the Python script


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
    print("Error: The file 'plot_dict.json' does not contain valid JSON.")#
#for key, value in plot_dict.items():
    #print(key,": ", value)

############################################################################################################
################################################ UI ########################################################

ui.page_title('PROTEUS')

def load_resources():
    print("loadding resources")
    app.add_static_files('/ui_images', 'ui_images')
    
load_resources()

with ui.header(elevated=True).style('background-color: #697689').classes('items-left justify-between h-12.5'):
    with ui.row().classes('w-full'):
        for module in modules.values():
            if module.type == 'Circulation':
                module.button = ui.button(module.moduleID, on_click=select_mod_id(module.moduleID), color=light_blue)
        shutdown_button = ui.button("Shutdown", on_click=shutdown_app, color="red")
        url_tag=ui.label("going online shortly..." ).style('font-size:150%')
with ui.footer(fixed=True).style('background-color: #a9b1be').props('width=100'):
    with ui.row().classes('w-full'):
        with ui.tabs() as tabs:
            tab_graphs = ui.tab('g', label = 'Module Control')
            tab_lem = ui.tab('l', label = 'LEM')
            tab_LabQ = ui.tab('q', label = 'LabQ')
            tab_advanced = ui.tab('p', label = 'ADVANCED CONTROLS')
            tab_image = ui.tab('i', label='PI&D')
            tab_historical_view = ui.tab('h', label='ANALYSE DATA')
            tab_software_update = ui.tab('f', label='Software Update')


with ui.tab_panels(tabs, value=tab_graphs).classes('w-full'):
    with ui.tab_panel(tab_graphs): 
        with ui.grid(columns=1).classes('items-start'):       
            with ui.grid(columns=5).classes('items-start'):
                new_experiment=ui.button("New Experiment", on_click=open_new_experiment_dialog, color='blue')
                sequence_button=ui.button('Select sequence', on_click=pick_seqfile)
                start_button=ui.button("Begin Sequence", on_click=start_btn_click, color='green')  
                stop_button = ui.button("STOP", on_click=stop_btn_click(), color='red')
                pause_button = ui.button("Pause Graphs", on_click=toggle_pause, color='green')
                
                experiment_file=ui.label('no experiment yet').classes('col-span-3 border p-1')
                experiment_file.style('font-size:120%')
                start_data_logging_button = ui.button("Start Data Logging", on_click=start_data_logging_btn_click, color='green')
                stop_data_logging_button = ui.button("Stop Data Logging", on_click=stop_data_logging_btn_click(), color='red') 
                retreive_logs_button = ui.button("Retrieve Logs", on_click=retreive_log_btn_clicks(), color='red')
                delete_all_logs_button = ui.button("Clear Cycler Logs", on_click=delete_all_logs_btn_click(), color='red')
                session_label = ui.label('')
                freeze_button=ui.button("Index Freeze Off", on_click=freeze_btn_click(), color='orange')
                index_dropdown = ui.select(label='Select Index', options=index_list).bind_value_to(index_value, "value")
                
                
                #add a log view that messages and data can be pushed to
            log = ui.log(max_lines=10).classes('w-full h-20')
            log.style('background-color: #f0f0f0; color: #333;')
            module_control_graph_= ui.column().classes('w-full')

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
        
    # 🔹 UI Setup for Historical Data Tab
    with ui.tab_panel(tab_historical_view):
        ui.label('Analyse Historical Data').classes('text-bold text-h6')

        # File Selection UI
        selected_file_label = ui.label('No file selected.')
        selected_file_path = {'path': None}
        ui.button("Browse Data Files", on_click=pick_data_file, color="blue")

        # Graph Display Area (3 columns, 2 rows)
        graph_area = ui.column().classes('w-full')

        # Button to Trigger Plotting
        ui.button("Load and Plot Data", on_click=load_and_plot_data, color="green")

    with ui.tab_panel(tab_software_update):
        load_software_update_tab()
            
line_updates = ui.timer(5, refresh_all)

for module in modules.values():
    if module.type == 'Circulation':
        select_mod_id(module.moduleID)()
        
ui.run(port=5500, reload=False)

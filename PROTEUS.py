from nicegui import ui, app
import threading
import time
import os
import pandas as pd
import subprocess
import sys
#import math
#import numpy as np
from datetime import datetime
from resource.local_file_picker import local_file_picker
import csv
import json
from typing import Callable
from pathlib import Path
import asyncio
import shutil
#import numpy as np
import plotly.graph_objects as go
from plotly_resampler import FigureResampler #requires 'pip install psutil
import signal
import sys
import psutil  # Requires `pip install psutil`
from tabs.software_update_tab import load_software_update_tab

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



class ValueContainer:
    def __init__(self, value):
        self.value = value

    def value_changed(self, new_value):
        print(f'Selected value: {new_value.value}')
        #index = new_value.value
        self.value = new_value


###################################################################################################
####################################### variables ##############################################

index_value = ValueContainer(1)
index_list = [i for i in range(1, 24)]
tubing_list = [13,14,16,19,25]
seqFilename = None  # Initialize the global variable to store the sequence file
processes = {}
modules = {}
circ_modules = []
ui_plots = {}
lem_module = None
experiment_folder_path =  os.path.join(os.getcwd(), "log")
paused = False  
timewindow = {'value':{ 'min': 0.20, 'max': 0.80}}
# COLOURS
light_blue = '#D9E3F0'
config = {}
moduleID=1001
proteus_version="version 250325.1"

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



###########################################################################################################
############################################# LOAD CONFIG ################################################



def load_config():
    global config
    config_file = 'configs/config.json'
    try:
        config = json.load(open(config_file, 'r'))
           #print('Proteus loaded config: ', config)
    except FileNotFoundError:
        print(f"Configuration file {config_file} was not found.")
    except json.JSONDecodeError:
        print(f"Configuration file {config_file} is not a valid JSON file.")


###########################################################################################################
############################################# DATA PROCESSING #############################################


def data_processing(df): 
    if df is not None:
        # Convert 'TIME' to datetime
        df['TIME'] = pd.to_datetime(df['TIME'])
        # Pump Calibration
        PumpCal = 0.004293
        df['Pump1_mLmin'] = (df['CIRCPUMPSPEED'])*PumpCal
        df['Pump2_mLmin'] = (df['PRESSUREPUMPSPEED'])*PumpCal

        df['Pressure_SP'] = (df['PRESSUREPID'])*(df['PRESSURESETPOINT'])
        df['Oxygen_SP'] = (df['OXYGENPID'])*(df['OXYGENSETPOINT'])

        # Calculate the rolling average
        df['FLOWMEASURED_rolling_avg'] = df['FLOWMEASURED'].rolling(60).mean()

        # Calculate the rolling average 
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
# same method but for historical data.
#should remove and use same method, passing dfh or df

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
    dfh['OUR'] = ((dfh['Pump2_mLmin'] / 1000) * (oxy_saturated - dfh['OXYGENMEASURED2']) + (dfh['PermeateFlow'] / 1000) * (oxy_saturated - dfh['OXYGENMEASURED2']))
    dfh['OUR_rollAvg_1min'] = dfh['OUR'].rolling(60).mean()
    dfh['OUR_rollAvg_5min'] = dfh['OUR'].rolling(300).mean()

    return dfh


############################################################################################################
################################################ FUNCTIONS #################################################

def subselect(module) -> None:  ## Subselect the data frame to get (limit) number of rows
    """Always selects the last 10,000 rows from module.data_frame for plotting.
    If there are fewer than 10,000 rows, it displays all available data."""
    if module.data_frame is not None:
        # Always take the last 10,000 rows or fewer if not available
        module.subset = module.data_frame.iloc[-10_000:].copy()

def module_list_update() -> None:   ## Create the modules from the serial_config file
    moduleID_local = 0
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
                moduleID_local = row[3]
                if int(moduleID_local)<config["LEM_ID_LIMIT"]:   #instruments with an ID >9000 (LEM LIMIT) are LEM modules
                    data_file = os.path.join(config["DATA_FOLDER"], f'{moduleID_local}_data.csv')
                    module = Module(moduleID_local, seqFilename=None, index=1, data_file=data_file)
                    modules[moduleID_local] = module
                    circ_modules.append(module.moduleID)
                    load_new_rows(module)
                    subselect(module)
                    data_processing(module.subset)
                elif int(moduleID_local)>=config["LEM_ID_LIMIT"]:
                    moduleID_local = row[3]
                    data_file = os.path.join(config["DATA_FOLDER"], f'{moduleID_local}_data.csv')
                    module = Module(moduleID_local, seqFilename=None, index=1, data_file=data_file)
                    module.type = 'LEM'
                    modules[moduleID_local] = module
                    lem_module=module.moduleID

def load_new_rows(module) -> None:
    if module.data_frame is None:
        start_row = 0
    else:    
        start_row = module.data_file_row

    if not os.path.exists(module.data_file):
        print(f"❌ {module.data_file} not found. No new rows loaded.")
        return 
    
    new_rows = pd.read_csv(module.data_file,dtype={"NULLEADER":str},names=config['COLNAMES'], skiprows=range(0, start_row + 1), on_bad_lines='skip')

    if not new_rows.empty:
        module.data_frame = pd.concat([module.data_frame, new_rows], ignore_index=True)
        module.data_file_row += len(new_rows)

def scan_for_modules() -> Callable[[], None]:  ## Scan for modules, this will start the module_register.py script
    def inner() -> None:
        global modules
        log.push("Scanning for modules...")
        if processes == {}:
            process = subprocess.Popen([sys.executable, config['MODULE_REGISTER_PATH'], '-s', '-c', config['SERIAL_CONFIG']])
        else:
            log.push("process already running, restart Proteus to scan again")
        #clear modules
        modules = {}
        module_list_update()
        message=(f"modules found are {list(modules)}")
        log.push(message)
    return inner

def null_session(target_module) -> None:   ## the 'Stop' button function, it stops the pumps and returns the valves to their 'off' state by running ALF with the null sequence
    global experiment_folder_path
    if experiment_folder_path is None:
        experiment_folder_path = os.path.join(os.getcwd(), "log")
    
    
    data_file_path = os.path.join(os.path.dirname(__file__), config["DATA_FOLDER"], f'{moduleID}_data.csv')
    log_file_path = os.path.join(experiment_folder_path, f'{moduleID}_log.csv')
    module_csv= os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
    if target_module in processes:
        processes[target_module].communicate(b"exit\n")
        print(f"Stopped {target_module} ALF session")
        time.sleep(1)
    alfi_session(seq_csv=config['NULLSEQUENCE'], 
                index=17, 
                data_csv=data_file_path, 
                log_csv=log_file_path,
                module_csv=module_csv,
                module_id=target_module)
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
    global experiment_folder_path

    # First, check if the sequence file has been selected
    if not seqFilename:
        # Trigger the file picker for selecting the sequence file
        log.push("awaiting a sequence file")
        await pick_seqfile("sequences")

    if seqFilename:
        # If sequence file is selected, proceed to folder selection
        def update_paths_to_save_locations(selected_folder):
            # Use the selected folder or fallback to the default log folder

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
        select_save_log_folder(callback=update_paths_to_save_locations,start_directory=experiment_folder_path,text= "choose where you want to log the data. \nCurrently "+experiment_folder_path)
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
    """Retrieve all files from the selected cycler's SD card, to a selected folder."""
    print("retrieving logs")
    #setup the actions that will happen when the correct save location is chosen.
    def update_paths_to_save_locations(selected_folder): 
        try:
            # Use the selected folder or fallback to the default log folder
            target_folder = selected_folder if selected_folder else os.path.join(os.getcwd(), "log")
            module_csv_path = os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
            data_file_path = os.path.join(os.path.dirname(__file__), config["DATA_FOLDER"], f'{moduleID}_data.csv')
            print("set files logs")
            run_retrieve_logs(moduleID,module_csv_path,target_folder,data_file_path)
            print("retrieved logs")
            
        except Exception as e:
            error_msg = f"-------------Error: retrieve_logs: {e}"
            print(error_msg)

    # Trigger the folder picker for selecting the destination folder
    print("callback defined")
    select_save_log_folder(callback=update_paths_to_save_locations,start_directory=experiment_folder_path,text= "choose where you want to save the data. \nCurrently "+experiment_folder_path)
    
def retrieve_log_btn_clicks() -> None:
    def inner():
        target_module = moduleID
        threading.Thread(target=retrieve_logs(target_module), daemon=True).start()
    return inner

def lem_stop_btn_click() -> None:
    def inner():
        global lem_module
        print(f"going to stop... {lem_module}")
        threading.Thread(target=null_session(lem_module), daemon=True).start()
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
        await select_experiment_folder()

    if seqFilename:
        # If sequence file is selected, proceed to folder selection
        #def on_folder_selected(selected_folder):
        # Use the selected folder or fallback to the default log folder
        def update_start_path(selected_folder):
            # Use the selected folder or fallback to the default log folder
            global experiment_folder_path
            experiment_folder_path = selected_folder if selected_folder else os.path.join(os.getcwd(), "log")
            
                        
            # Now run the sequence using the selected log folder and selected sequence file
            data_file_path = os.path.join(os.path.dirname(__file__), config["DATA_FOLDER"], f'{moduleID}_data.csv')
            copy_data_file_to_path = os.path.join(experiment_folder_path, f'{moduleID}_data.csv')
            log_file_path = os.path.join(experiment_folder_path, f'{moduleID}_log.csv')  # Use chosen folder
            module_csv_path = os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
            
            # Copy the sequence file to the selected folder
            try:
                sequence_dest_path = os.path.join(experiment_folder_path, os.path.basename(seqFilename))
                shutil.copy(seqFilename, sequence_dest_path)
            except Exception as e:
                print(f"Error copying sequence file: {e}")
        
            log.push(f"Sequence file copied to: {sequence_dest_path}")
            experiment_file.set_text("Experiment filed in :" + experiment_folder_path)
            
            alfi_session(index=index_value.value, 
                         seq_csv=seqFilename, 
                         data_csv=data_file_path, 
                         log_csv=log_file_path, 
                         module_csv=module_csv_path,
                         experiment_file_path=copy_data_file_to_path,
                         module_id=moduleID)


    # Trigger the folder picker after sequence file selection
        
        select_save_log_folder(callback=update_start_path,start_directory=experiment_folder_path,text= "Choose the experiment folder you wish to use. \nCurrently "+experiment_folder_path)
        
    else:
        print("Sequence file not selected, cannot start sequence.")


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



def select_save_log_folder(callback, start_directory: str = os.getcwd(),text='default text')->None:
    """ use to select a directory to save data."""
    print("start_directory sent "+start_directory)
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
    with ui.dialog().classes('flex justify-center items-center') as folder_dialog, ui.card():
        ui.label(f'{text} ').classes('text-center')

        file_grid = ui.aggrid({
            'columnDefs': [{'field': 'name', 'headerName': 'File'}],
            'rowSelection': 'single',
        }).on('cellDoubleClicked', handle_double_click)

        with ui.row().classes('w-full justify-end'):
            ui.button('Cancel', on_click=folder_dialog.close).props('outline')
            ui.button('Select', on_click=handle_select)

    update_file_grid()  # Load the initial directory contents
    folder_dialog.open()  # Open the
    #print("the current directory is ",current_directory)
 
    
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
                 experiment_file_path = None,
                 module_id = None) -> None:
    
    if module_id is None:
        print("module_id is none - not executing alfie session")

    global experiment_folder_path  # Access the experiment folder path
    
    # Ensure we have a valid experiment folder, fallback to default log folder if not created
    if experiment_folder_path is None:
        experiment_folder_path = os.path.join(os.getcwd(), "log")

    # Define the log file path within the experiment folder
    log_file_path = os.path.join(experiment_folder_path, f'{module_id}_log.csv')
    
    # See ALF.py for the command line arguments
    if module_id in processes:
        if processes[module_id].poll() is None:
            print(f"ALFI script already running for {module_id}, poll: {processes[module_id].poll()}")
            return
    
    cmd_args = [config['ALF_FILEPATH'] , '-u', str(module_id)]
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
    processes[module_id] = subprocess.Popen([sys.executable] + cmd_args, stdin=subprocess.PIPE)
    module = modules[module_id]
    module.seqFilename = seq_csv
    module.index = index
    module.freeze = freeze
    module.session_label = f"Sequence: {module.seqFilename}, Index = {module.index}, Freeze = {module.freeze}"
    print(f"ALFI started sequence file for {module_id}, index = {module.index}, seqFilename = {module.seqFilename}")
    session_label.text = module.session_label
    print('updated session label for module ', module_id, ' to ', module.session_label)

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
    global moduleID
    module_list_update()
    module_set.clear()
    with module_set:
        for module in modules.values():
            if module.type == 'Circulation':
                module.button = ui.button(module.moduleID, on_click=select_mod_id(module.moduleID), color = 'blue' if moduleID == module.moduleID else 'lightblue')
                
    #update the url displayed
    #print(f"app.url len ... {len(app.urls)}")
    if len(app.urls)>=2:
        LAN_ID="nothing connected"
        for url in app.urls:
            #print(url)
            if '192' or '10.' in url:
                LAN_ID=url
        url_tag.set_text('available on the internal LAN on '+LAN_ID)
    if len(app.urls)==1:
            url_tag.set_text('standalone version. No remote access')
    if paused:
        log.push("⏸ Graph updates paused.")
        return  # ✅ Stop refreshing if paused
    if modules=={}:
        log.push("no modules are connected.")
        return  # ✅ continue without refresh as there are no modules 

    if moduleID not in modules.keys():
        moduleID=list(modules.keys())[0]
    module = modules[moduleID]

    module.len_of_datafile= count_rows(module.data_file)
    if module.len_of_datafile > module.data_file_row:
        load_new_rows(module)
        module.data_file_row = module.len_of_datafile
        #print(f"Data file updated for module {moduleID}, data file row = {module.data_file_row}")
    subselect(module)
    data_processing(module.subset)
    update_line_plot()

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

async def pick_seqfile(defaultFolder) -> None: # uses local_file_picker to select files for sequences
    global seqFilename
    result = await local_file_picker(os.path.join(os.getcwd(), defaultFolder),text="Double-click to choose a sequence to run", multiple=True)        
    seqFilename = result[0] if result else ""
    sequence_file.text = f"Sequence: {os.path.basename(seqFilename)}" if seqFilename else ""
    print(f"Selected file: {seqFilename}")
    
async def pick_sequence_file() -> None: # uses local_file_picker to select files for sequences
    global seqFilename
    result = await local_file_picker(os.path.join(os.getcwd(), "sequences"),text="Double-click to choose a sequence to run", multiple=True)        
    seqFilename = result[0] if result else ""
    sequence_file.text = f"Sequence: {os.path.basename(seqFilename)}" if seqFilename else ""
    print(f"Selected file: {seqFilename}")
    
async def select_experiment_folder() -> None: # uses local_file_picker to select files for sequences
    global seqFilename
    result = await local_file_picker(os.path.join(os.getcwd(), "experiments"),text="Double-click to choose where to save the experiment", multiple=True)        
    seqFilename = result[0] if result else ""
    sequence_file.text = f"Sequence: {os.path.basename(seqFilename)}" if seqFilename else ""
    print(f"Selected file: {seqFilename}")
    
async def pick_data_file():# 🔹 File Picker Function
    result = await local_file_picker(os.path.dirname(__file__), multiple=False)
    if result:
        selected_file_path['path'] = result[0]
        selected_file_label.text = f"Selected file: {os.path.basename(selected_file_path['path'])}"
        print(f"Selected file: {selected_file_path['path']}")
    else:
        selected_file_label.text = "No file selected."


def build_lem_seq(media, circ_module, volume) -> None: # Used to build the LEM sequence
    df = pd.read_csv(config['LEM_SEQ_PATH'])
    print(df)

    lem_dispense_target_volume = config['LEM_DISPENSE_TARGET_VOLUME']
    lem_dispense_actual_volume = config['LEM_DISPENSE_ACTUAL_VOLUME']

    df.at[1, 'dispenseVolumeSP'] = (volume * int(lem_dispense_target_volume))/int(lem_dispense_actual_volume)
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
    #print(df)
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
        LEMlog.push(f"Dispensing {lem_volume_input.value} ml  {media} in {circ_module}")
        build_lem_seq(media,circ_module,lem_volume_input.value)
        if not lem_module in processes:
            #active_circulation_module=moduleID
            #moduleID=lem_module
            # print(f"Dispensing {lem}")
            module_csv_path= os.path.join(os.path.dirname(__file__), config["SERIAL_CONFIG"])
            alfi_session(seq_csv=config['LEM_SEQ_PATH'], module_csv=module_csv_path,module_id=lem_module)
            #moduleID=active_circulation_module
    return inner

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

#####shutdown processes###########################################################################################


def show_confirmation_dialog():
    # Create a confirmation dialog
    with ui.dialog() as dialog:
        with ui.card():
            ui.label("Are you sure?").classes('text-lg text-center')
        with ui.row().classes('w-full justify-center'):
            ui.button('No', on_click=dialog.close,color='green')  # Close the dialog if No
            ui.button('Yes', on_click=handle_yes(dialog), color='red')

    dialog.open()  # Open the dialog

def handle_yes (dialog):
    # What happens when "Yes" is clicked
    #print("oi")
    dialog.close()
    time.sleep(1)
    print("getting here")
    ui.run_javascript('window.close()')
    #shutdown_app()

def shutdown_app():
    """Stops all Python processes related to Proteus and exits the UI safely."""

    print("stopping ALF session...")
    
    stop_data_logging_btn_click()       
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
    
# used on restart button on the update tab
def terminate_all_processes():
    print("🧹 Terminating tracked subprocesses...")
    for name, proc in processes.items():
        try:
            print(f"💀 Terminating '{name}'")
            proc.terminate()
            proc.wait(timeout=3)
        except Exception as e:
            print(f"⚠️ Could not terminate '{name}': {e}")
    
async def restart_proteus():
    terminate_all_processes()
    print("🔁 Restarting PROTEUS.py now...")
    ui.run_javascript('window.close()')
    await asyncio.sleep(1)  # ⏳ Let the browser process it
    os.execl(sys.executable, sys.executable, *sys.argv)



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
    print("loading resources")
    app.add_static_files('/ui_images', 'ui_images')
    
load_resources()

with ui.header(elevated=True).style('background-color: #697689').classes('items-left justify-between h-12.5'):
    with ui.row().classes('w-full') as module_set:
        for module in modules.values():
            if module.type == 'Circulation':
                module.button = ui.button(module.moduleID, on_click=select_mod_id(module.moduleID), color=light_blue)
    ui.button('Scan for Modules', on_click=scan_for_modules())
    shutdown_button = ui.button("Shutdown", on_click=show_confirmation_dialog, color="red")
    url_tag=ui.label("going online shortly..." ).style('font-size:130%')
    ui.space()
    ui.space()
    session_label = ui.label('').style('font-size:130%')
        
with ui.footer(fixed=True).style('background-color: #a9b1be').props('width=100'):
    with ui.row().classes('w-full'):
        with ui.tabs() as tabs:
            tab_graphs = ui.tab('g', label = 'Module Control')
            tab_image = ui.tab('i', label='P&ID')
            tab_historical_view = ui.tab('h', label='ANALYSE DATA')
            tab_lem = ui.tab('l', label = 'LEM')
            tab_software_update = ui.tab('f', label='Software Update')
            tab_about=ui.tab('a', label= 'About Proteus')


with ui.tab_panels(tabs, value=tab_graphs).classes('w-full'):
    with ui.tab_panel(tab_graphs): 
        with ui.grid(columns=1).classes('items-start'):       
            with ui.grid(columns=5).classes('items-start'):
                new_experiment=ui.button("Select/New Experiment", on_click=open_new_experiment_dialog, color='blue')
                experiment_file=ui.label('no experiment yet').classes('col-span-2 border p-1')
                experiment_file.style('font-size:120%')
                start_button=ui.button("Begin Sequence", on_click=start_btn_click, color='green')  
                stop_button = ui.button("Stop Cycler", on_click=stop_btn_click(), color='red')
                
                sequence_button=ui.button('Select sequence', on_click=pick_sequence_file, color='blue')
                sequence_file=ui.label('no sequence yet').classes('col-span-2 border p-1')
                sequence_file.style('font-size:120%')  
                start_data_logging_button = ui.button("Start Data Logging", on_click=start_data_logging_btn_click, color='green')
                stop_data_logging_button = ui.button("Stop Data Logging", on_click=stop_data_logging_btn_click(), color='red')
                
                pause_button = ui.button("Pause Graphs", on_click=toggle_pause, color='green')
                retreive_logs_button = ui.button("Retrieve Logs", on_click=retrieve_log_btn_clicks(), color='red')
                delete_all_logs_button = ui.button("Clear Cycler Logs", on_click=delete_all_logs_btn_click(), color='red')
                freeze_button=ui.button("Index Freeze Off", on_click=freeze_btn_click(), color='orange')
                index_dropdown = ui.select(label='Select Index', options=index_list).bind_value_to(index_value, "value")
                
                
                #add a log view that messages and data can be pushed to
            log = ui.log(max_lines=10).classes('w-full h-20')
            log.style('background-color: #f0f0f0; color: #333;')
            module_control_graph_= ui.column().classes('w-full')


    with ui.tab_panel(tab_lem):
        media_list=config['MEDIA_LIST']

        with ui.grid(columns=5):
            ui.space()
            lem_volume_input=ui.number(label='Volume (mL)', value=2, format='%.2f')
            ui.space()
            lem_stop_btn=ui.button('STOP LEM', on_click=lem_stop_btn_click(), color='RED')
            ui.space()
        
        with ui.element('div').classes('grid-container').style(f'''
            display: grid;
            grid-template-columns: repeat({len(modules)}, 80px);
            gap: 10px;
        '''):
            #with ui.grid(columns=len(modules)):
            print(f"{len(modules)}")
            ui.space()
            for module in circ_modules:
                ui.label(module)
            for i in range(0,4):
                ui.label(media_list[i])
                for module in circ_modules:
                    ui.button(f'DISPENSE', on_click=lem_dispense(media_list[i],module), color=light_blue)
        LEMlog = ui.log(max_lines=10).classes('w-full h-20')
        LEMlog.style('background-color: #f0f0f0; color: #333;')

    # New Image tab panel
    with ui.tab_panel(tab_image):
        ui.image('resource/PI&DImage.png').style('width: 100%; height: auto; display: block; margin: 0 auto;')

    # 🔹 UI Setup for Historical Data Tab
    with ui.tab_panel(tab_historical_view):
        ui.label('Analyse Historical Data')

        # File Selection UI
        selected_file_label = ui.label('No file selected.')
        selected_file_path = {'path': None}
        ui.button("Browse Data Files", on_click=pick_data_file, color="blue")

        # Graph Display Area (3 columns, 2 rows)
        graph_area = ui.column().classes('w-full')

        # Button to Trigger Plotting
        ui.button("Load and Plot Data", on_click=load_and_plot_data, color="green")
    
    # About  tab panel
    with ui.tab_panel(tab_about):
        ui.label("Proteus cycler software.").classes('justify-self-center')
        ui.label(proteus_version).classes('justify-self-center')
        ui.label("Copyright Cellular Agriculture 2025").classes('justify-self-center')
        
    with ui.tab_panel(tab_software_update):
        load_software_update_tab(on_restart=restart_proteus)
            
line_updates = ui.timer(config['GRAPH_UPDATE_RATE'], refresh_all)

for module in modules.values():
    if module.type == 'Circulation':
        select_mod_id(module.moduleID)()
ui.run(native=(config['NATIVE']),port=5503, reload=False)

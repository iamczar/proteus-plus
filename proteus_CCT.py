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


###########################################################################################################
#############################################  CONSTANTS  #################################################
###########################################################################################################

ALFEXECUTABLE = 'ALF.py' # The ALF executable file
# ALFEXECUTABLE = 'FAKE_ALF.py' # The ALF executable file
plot_points = 300 # Number of rows to display in the plots
nullsequencecsv = f'Null_sequence_cycler.csv' # The null sequence file, used to stop circ modules.
default_moduleID = '2503'
colnames=["TIME",'NULLEADER', 'MODUID', 'COMMAND', 'STATEID', "OXYMEASURED", "PRESSUREMEASURED",
        "FLOWMEASURED", "TEMPMEASURED", "CIRCPUMPSPEED", "PRESSUREPUMPSPEED", "PRESSUREPID", "PRESSURESETPOINT", "PRESSUREKP",
        "PRESSUREKI", "PRESSUREKD", "OXYGENPID", "OXYGENSETPOINT", "OXYGENKP", "OXYGENKI", "OXYGENKD", "OXYGENMEASURED1", "OXYGENMEASURED2",
        "OXYGENMEASURED3", "OXYGENMEASURED4", "NULLTRAILER", "Unknown"]
SERIALCONFIGFILE = 'serial_config.csv'
PYTHONEXECUTABLE = sys.executable

def data_processing(df):  ## Process the data subset for calibration, offset, etc.
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

processes = {}
modules = {}
ui_plots = {}


# COLOURS
light_blue = '#D9E3F0'

############################################################################################################
################################################ FUNCTIONS #################################################



def subselect(module) -> None:  ## Subselect the data frame to get (limit) number of rows
    global plot_points
    print(f"Subselecting {module.moduleID} data frame")
    module.subset = None
    if module.data_frame is not None:
        if len(module.data_frame) > plot_points:
            # Calculate the starting row
            starting_row = int(len(module.data_frame) * timewindow['value']['min'])
            finish_row = int(len(module.data_frame) * timewindow['value']['max'])
            print(len(module.data_frame))
            print(timewindow['value']['max'])
            print('start and finish:')
            print(starting_row)
            print(finish_row)
            target_rows = finish_row - starting_row
            # plot_points = min(target_rows,300)
            # select evenly spaced rows in the range
            module.subset = module.data_frame.iloc[starting_row:finish_row:math.ceil(target_rows/plot_points)].copy()

        else:
            # Select the last 'plot_points' number of rows
            module.subset = module.data_frame[-plot_points:].copy()
    print(module.subset)

def module_list_update() -> None:   ## Create the modules from the serial_config file
    global modules
    modules = {}
    with open(SERIALCONFIGFILE, mode='r') as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            moduleID = row[3]
            data_file = f'{moduleID}_data.csv'
            module = Module(moduleID, seqFilename=None, index=1, data_file=data_file)
            modules[moduleID] = module
            load_new_rows(module)
            subselect(module)
            data_processing(module.subset)

def load_new_rows(module) -> None:  ## Load new rows from the data file into the data frame
    if module.data_frame is None:
        start_row = 0
    else:    
        start_row = module.data_file_row
    print(f"Loading new rows for {module.moduleID} from row {start_row}")
    new_rows = pd.read_csv(module.data_file, names=colnames, skiprows=range(0, start_row), on_bad_lines='skip')
    print(new_rows)
    if not new_rows.empty:
        print(new_rows)
        module.data_frame = pd.concat([module.data_frame, new_rows], ignore_index=True)
        module.data_file_row = module.data_file_row + len(new_rows)
    if module.subset is not None:    
        update_line_plot()

def scan_for_modules() -> Callable[[], None]:  ## Scan for modules, this will start the module_register.py script
    def inner() -> None:
        print("Scanning for modules...")
        if processes == {}:
            process = subprocess.Popen([PYTHONEXECUTABLE, 'module_register.py', '-s'])
        else:
            print("process already running, restart Proteus to scan again")
        global modules
        modules = {}
        module_list_update()
    return inner

def null_session() -> None:   ## the 'Stop' button function, it stops the pumps and returns the valves to their 'off' state by running ALF with the null sequence
    alfi_session(seq_csv=nullsequencecsv, index=16)
    print(f"Pumps stopped & valves returned to natural state.")
    time.sleep(1)
    if moduleID in processes:
        processes[moduleID].communicate(b"exit\n")
        print(f"Stopped {moduleID} null sequence")
    else:
        print(f"No null sequence running for {moduleID}")

def stop_btn_click() -> None:
    threading.Thread(target=null_session, daemon=True).start()

def freeze_btn_click() -> None:
    global freeze
    freeze = not freeze
    if freeze:
        freeze_button.props('color=purple')
        freeze_button.text = "Freeze On"
    else:
        freeze_button.props('color=orange')
        freeze_button.text = "Freeze Off"

def start_btn_click() -> None:
    alfi_session(index=index_value.value, seq_csv=seqFilename)

def alfi_session(debug=False, seq_csv=None, log_csv=None, baud=None, pause=False, module_csv=None, data_csv=None, index=None, serial_config=None, port=None) -> None:
    # See ALF.py for the command line arguments
    if moduleID in processes:
        if processes[moduleID].poll() is None:
            print(f"ALFI script already running for {moduleID}, poll: {processes[moduleID].poll()}")
            return
    
    cmd_args = [ALFEXECUTABLE , '-u', str(moduleID)]
    if debug:
        cmd_args.append('--debug')
    if seq_csv:
        cmd_args.extend(['-q', seq_csv])
    if log_csv:
        cmd_args.extend(['-l', log_csv])
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
        
    print(cmd_args)
    processes[moduleID] = subprocess.Popen([PYTHONEXECUTABLE] + cmd_args, stdin=subprocess.PIPE)
    module = modules[moduleID]
    module.seqFilename = seq_csv
    module.index = index
    module.freeze = freeze
    module.session_label = f"Sequence: {module.seqFilename}, Index = {module.index}, Freeze = {module.freeze}"
    print(f"ALFI started sequence file for {moduleID}, index = {module.index}, seqFilename = {module.seqFilename}")
    session_label.text = module.session_label
    print('updated session label for module ', moduleID, ' to ', module.session_label)

def count_rows(csv_file):
    with open(csv_file, 'r') as f:
        for i, _ in enumerate(f, 1):
            pass
    return i

def refresh_all() -> None:
    module = modules[moduleID]
    module.len_of_datafile= count_rows(module.data_file)
    if module.len_of_datafile > module.data_file_row:
        load_new_rows(module)
        module.data_file_row = module.len_of_datafile
        print(f"Data file updated for module {moduleID}, data file row = {module.data_file_row}")
    subselect(module)
    data_processing(module.subset)
    update_line_plot()

def update_line_plot() -> None:
    module = modules[moduleID]
    for plot in plot_dict.values():
        y_values = [module.subset[y].values for y in plot['y_values']]
        x_values = module.subset['TIME'].values  # 'TIME' is already datetime
        ui_plots[plot['name']].clear()
        ui_plots[plot['name']].push(x_values, y_values)
        # if 'y_limits' in plot['kwargs'] and plot['kwargs']['y_limits'] is not None:
        #     ui_plots[plot['name']].fig.gca().set_ylim(plot['kwargs']['y_limits'])
        #     ui_plots[plot['name']].update()

def select_mod_id(value) -> Callable[[], None]: # Used to select the active module by mod ID.
    def inner() -> None:
        global moduleID
        moduleID = value
        for module in modules.values():
            color = 'blue' if moduleID == module.moduleID else 'lightblue'
            module.button.props(f'color={color}')
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

############################################################################################################
##########################################  SETUP AND RUN  #################################################

freeze = False
moduleID = default_moduleID

cwd = os.getcwd()
if os.getcwd()!=os.path.abspath(__file__):
    print("Current Working Directory: ", os.getcwd())
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("New Working Directory: ", os.getcwd())

module_list_update()

try:
    with open('plot_dict.json', 'r') as f:
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
            module.button = ui.button(module.moduleID, on_click=select_mod_id(module.moduleID), color=light_blue)

with ui.footer(fixed=True).style('background-color: #a9b1be').props('width=100'):
    with ui.row().classes('w-full'):
        with ui.tabs() as tabs:
            tab_graphs = ui.tab('g', label = 'Module Control')
            tab_pumpCal = ui.tab('p', label = 'Port Scan')

with ui.tab_panels(tabs, value=tab_graphs).classes('w-full'):
    with ui.tab_panel(tab_graphs): 
        with ui.grid(columns=1).classes('items-start'):       
            with ui.grid(columns=5).classes('items-start'):
                ui.space()     
                ui.space()
                ui.button("STOP", on_click=stop_btn_click, color='red')     
                ui.space()     
                ui.space()    
                sequence_button=ui.button('Select sequence', on_click=pick_seqfile)
                index_dropdown = ui.select(label='Select Index', options=index_list).bind_value_to(index_value, "value")
                freeze_button=ui.button("Index Freeze Off", on_click=freeze_btn_click, color='orange')
                start_button=ui.button("Begin Sequence", on_click=start_btn_click, color='green') 
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
                    line_plot = ui.line_plot(n=plot['number_of_lines'], limit=plot_points,) \
                                            .with_legend(plot['legend'])
                    ax = line_plot.fig.gca()  # Get the current Axes instance on the current figure
                    ax.set_xlabel('Time (hours)')
                    ax.set_ylabel(plot['y_label'])
                    ax.set_title(plot['title'])
                    # if 'y_limits' in plot:
                    #     ax.set_ylim(plot['y_limits'])  # Correctly set y-axis limits here
                    ui_plots[plot['name']] = line_plot

    with ui.tab_panel(tab_pumpCal):
        ui.button('Scan for Modules', on_click=scan_for_modules())

line_updates = ui.timer(5, refresh_all)

ui.run(port=5500)
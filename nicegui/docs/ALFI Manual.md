# ALFI
### Index
1. Structure
    * Required Libraries
2. Files of ALFI
    * ALF.py
    * unifiedstableV02i5.cpp
    * Proteus.py
    * config.json
        * Table: keys for configuration
    * 2501_sequence.csv
        * Heading Descriptions and Value Ranges for XXXX_sequence.csv 
    * serial_config.csv
        * Headings and Values for serial_config.
    * plot_dict.json
    * XXXX_data.csv  
    * XXXX_log.csv
3. Nomenclature



## Structure:
```
|--\PROTEUSLIVE
|   |
|   |--proteus.py
|   |--config.json
|   |--local_file_picker.py
|   |
|   |--\scripts
|   |   |--ALF.py
|   |   |--module_register.py
|   |
|   |--\configs
|   |   |--serial_config.csv
|   |   |--plot_dict.json
|   |
|   |--\sequences
|   |   |--\system sequences
|   |   |   |--SYS_SEQ_NULL.csv
|   |   |   |--SYS_SEQ_PUMP_CALS.csv
|   |   |   |--SYS_SEQ_LEM.csv
|   |   |
|   |   |--\harvest
|   |   |   |--ALP-CC001-02-drain_pump1_test.csv
|   |   |   |--2501_sequence_03-Drain-ECS-only-022-fast60mLmin-A0.csv
|   |   |   |--etc etc etc
|   |   |
|   |   |--\module tests
|   |   |   |--circ_valve_test.csv
|   |   |   |--lem_valve_test.csv
|   |
|   |--\data
|   |   |--XXXX_data.csv
|   |
|   |--\log
|   |   |--XXXX_log.csv

```
## Required Libraries
For Python: pyserial, numpy, pandas, nicegui.

For Arduino: PID and Stepper libraries. 
 

## Files
### ALF.py
ALF.py is the serial interface script. It's prmary function is to load **_sequences_** and pass them to the Arduino microcontroller when they are requested. It will also log **_dispatches_** and **_replies_** to and from the Arduino, and also store **_module data reports_** for later use.

### unifiedstableV02i5.cpp
unifiedstableV02i5.cpp will run on the Arduino. It will control **_valve states_**, **_control loops_**, and **_transition functions_**.

This is the code for the arduino microcontroller. designed for Arduino MEGA, though others may also work. It should be uploaded to the Arduino with the ArduinoIDE. This will need the PID and Stepper libraries. Copy the code and paste into the IDE. It will likely output a fallthrough warning, which is safe to ignore.

### proteus.py
Proteus is the primary user interface for ALFI. it displays operational data, scans for active modules, allows the starting and halting of sequences (via ALF sessions). These include operational sequences for culture, drain and sterilise cycles, and LEM sequences for media or other additions.

### config.json
config.json holds the configuration information, used by both ALF and Proteus. 

| Parameter | Value | Description |
| --- | --- | --- |
| ALF_FILEPATH | scripts\\ALF.py | Path to the ALF.py script |
| SERIAL_CONFIG | configs\\serial_config.csv | Path to the serial configuration file |
| NULLSEQUENCE | sequences\\system sequences\\SYS_SEQ_NULL.csv | Path to the null sequence file |
| PLOT_DICT | configs\\plot_dict.json | Path to the plot dictionary file |
| PLOT_POINTS | 300 | Number of points to plot |
| COLNAMES | ["TIME", "NULLEADER", "MODUID", "COMMAND", "STATEID", "OXYMEASURED", "PRESSUREMEASURED", "FLOWMEASURED", "TEMPMEASURED", "CIRCPUMPSPEED", "PRESSUREPUMPSPEED", "PRESSUREPID", "PRESSURESETPOINT", "PRESSUREKP", "PRESSUREKI", "PRESSUREKD", "OXYGENPID", "OXYGENSETPOINT", "OXYGENKP", "OXYGENKI", "OXYGENKD", "OXYGENMEASURED1", "OXYGENMEASURED2", "OXYGENMEASURED3", "OXYGENMEASURED4", "NULLTRAILER", "Unknown"] | Column names for the data |
| MEDIA_LIST | ["Media 1", "Media 2", "Flush", "Sterilant"] | List of media types |
| LEM_SEQ_PATH | sequences\\system sequences\\LEM_SEQ.csv | Path to the LEM sequence file |
| LEM_PORT_CIRCS | ["2501", "2502", "2503", "2504"] | List of LEM port circuits |

### XXXX_sequence.csv
XXXX_sequence is an example **_sequence_** file, with each line as a **_state_** which can be edited to meet process demands. it will run top to bottom, with the PC dispatching the next state to the Arduino when a transition criteria is met.

A sequence file can loosely be broken down into two regions. To the left are process variables, such as valve states, control loop flags, and transition functions. To the right is hardware config, such as physical pin connections, calibration values, and system config.

#### Sequence Explainer:

| Valve1 | Valve2 | Pump | ControlLoop1 | TransTime | TimeSP | 
| --- | --- | --- | --- | --- | --- | 
| 0 | 0 | 0 | 0 | 0 | 0 | 
| 0 | 1 | 1 | 1 | 1 | 30s | 
| 1 | 1 | 0 | 0 | 1 | 45s | 

Here, the first row is the NULL state. It has no valves active.

In the second row, Valve2 and Pump are open, and ControlLoop1 is enabled. The TransTime control loop is enabled, and will request a transition to the next state after 30 seconds.

In the third row, Valve1 and Valve2 are open, and ControlLoop1 is disabled. The TransTime control loop is enabled, and will request a transition to the next state after 45 seconds.

### serial_config.csv
serial_config.csv is used to tell ALF the COM ports of all modules attached to it. It can be manually configured, or set using module_register.py, normally run from proteus on the "port scan" tab.

### plot_dict.json.csv
plot_dict.json is used to hold configuration information for the displayed operational data.

### XXXX_data.csv
XXXX_data.csv is the data log file, which will be updated with each module report. Each module has it's own data file.

### XXXX_log.csv
XXXX_log.csv is the log file, which will be updated with each dispatch and reply. Each module has it's own log file.

## Heading Descriptions and Value Ranges for XXXX_sequence.csv 

| Position | Heading | Type | Description |
| --- | --- | --- | --- |
| 1 | nullLeader | int | Always leave as Zero |
| 2 | modId | int | 0000-9999 |
| 3 | command | int | At the moment, only 1002 - PC_STATE_DISPATCH is implimented for sequences |
| 4 | stateId | int |Can be anything, it will show as part of the module sensor and data report, to inform operations |
| 5 | circFlow | double |-1 - 9999, MODAL: -1 means use PID control. any positive number is a flowrate setpoint for the Circulation pump. |
| 6 | pressureFlow | double |-1 - 9999 MODAL: -1 for PID, any positive number is a flowrate setpoint for the back pressure pump. |
| 7 | valve1 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 8 | valve2 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 9 | valve3 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 10 | valve4 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 11 | valve5 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 12 | valve6 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 13 | valve7 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 14 | valve8 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 15 | valve9 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 16 | valve10 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 17 | valve11 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 18 | valve12 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 19 | valve13 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 20 | valve14 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 21 | valve15 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 22 | valve16 | bool | 0 or 1, valve is energised on 1, actual flow depends on valve NC or NO |
| 23 | transTimeFlag | bool | Flag to enable Time-based state Transitions.|
| 24 | transTimeSp | long | Time in ms to run until requesting new state.|
| 25 | pressureSP | double | Target Pressure for PID control|
| 26 | oxySP | double | Target oxy for PID control|
| 27 | presInterval | double | Time in ms between pressure measurements.|
| 28 | flowInterval | double | Time in ms between flow measurements|
| 29 | oxyInterval | double | Time in ms between oxy measurements.|
| 30 | reportInterval | double | Time in ms between data reports|
| 31 | oxyTemp | float | N/A, leave blank  |
| 32 | oxyCircChannel | int | Channel of Oxy to use for PID control|
| 33 | pumpSpeedRatio | float | The maximum speed of pump 2, relative to pump 1.|
| 34 | circPumpCal | float | Volume per step for circ pump (pump 1)|
| 35 | pressurePumpCal | float | Volume per step for pressure pump (pump 2)|
| 36 | pressureKp | double | Pressure PID variable.|
| 37 | pressureKi | double | Pressure PID variable.|
| 38 | pressureKd | double | Pressure PID variable.|
| 39 | oxyKp | double | Oxy PID variable.|
| 40 | oxyKi | double | Oxy PID variable.|
| 41 | oxyKd | double | Oxy PID variable.|
| 42 | flowInstalled | int |0 or 1. 1 if I2C flow sensor is connected |
| 43 | pressureInstalled | int |0 or 1. 1 if pressure sensor (analogue type) is connected |
| 44 | oxyInstalled | int | 0 or 1. 1 if oxy is connected|
| 45 | activeOxyChannel1 | int | 0 or 1. if 1, it will request data from oxy channel 1|
| 46 | activeOxyChannel2 | int | 0 or 1. if 1, it will request data from oxy channel 2|
| 47 | activeOxyChannel3 | int | 0 or 1. if 1, it will request data from oxy channel 3|
| 48 | activeOxyChannel4 | int | 0 or 1. if 1, it will request data from oxy channel 4|
| 49 | pump1Cw | bool | pump direction control pin. |
| 50 | pump2Cw | bool | pump direction control pin. |
| 51 | pump3Cw | bool | pump direction control pin. |
| 52 | pump4Cw | bool | pump direction control pin. |
| 53 | pump1DirPin | int | The physical pin number for the pump.|
| 54 | pump1StepPin | int | The physical pin number for the pump.|
| 55 | pump2DirPin | int | The physical pin number for the pump.|
| 56 | pump2StepPin | int | The physical pin number for the pump.|
| 57 | pump3DirPin | int | The physical pin number for the pump.|
| 58 | pump3StepPin | int | The physical pin number for the pump.|
| 59 | pump4DirPin | int | The physical pin number for the pump.|
| 60 | pump4StepPin | int | The physical pin number for the pump.|
| 61 | valve1Pin | int | The physical pin number for the Valve.|
| 62 | valve2Pin | int | The physical pin number for the Valve.|
| 63 | valve3Pin | int | The physical pin number for the Valve.|
| 64 | valve4Pin | int | The physical pin number for the Valve.|
| 65 | valve5Pin | int | The physical pin number for the Valve.|
| 66 | valve6Pin | int | The physical pin number for the Valve.|
| 67 | valve7Pin | int | The physical pin number for the Valve.|
| 68 | valve8Pin | int | The physical pin number for the Valve.|
| 69 | valve9Pin | int | The physical pin number for the Valve.|
| 70 | valve10Pin | int | The physical pin number for the Valve.|
| 71 | valve11Pin | int | The physical pin number for the Valve.|
| 72 | valve12Pin | int | The physical pin number for the Valve.|
| 73 | valve13Pin | int | The physical pin number for the Valve.|
| 74 | valve14Pin | int | The physical pin number for the Valve.|
| 75 | valve15Pin | int | The physical pin number for the Valve.|
| 76 | valve16Pin | int | The physical pin number for the Valve.|
| 77 | oxyConfigParameter | int | |
| 78 | pressure0Address | double | |
| 79 | pressureChannel | double | |
| 80 | flow0Address | double | |
| 81 | dispensePara | int | N/A, leave blank |
| 82 | dispenseVolumeSP | int | used for volume transitions. mostly set automatically in LEM control. |
| 83 | pcBaudRate | int | 115200, leave as is |
| 84 | oxyBaudRate | int | 115200, leave as is  |
| 85 | pressureBaudRate | int | 115200, leave as is  |
| 86 | flagCheck | int | N/A, leave blank |
| 87 | nullTrailer | int | Always leave as Zero |

## serial_config.csv
ALF.py will look for this file at startup. It is used to tell it where to look for modules. If in a Linux enviroment, like a RaspPi, they will look something like \dev\ttyACM0. In a windows enviroment, they will be something like COM4. as default, all baudrates are 115200. If this needs to be changed, it will also require a change to be made in the Arduino code.

## Headings and Values for serial_config.csv
| port | baud_rate | timeout | circmodid |
| --- | --- | --- | --- |
| \dev\ttyACM0 | 115200 | 1 | 2501 |
| 0 | 0 | 1 | 2502 |
| 0 | 0 | 1 | 2503 |
| 0 | 0 | 1 | 2504 |

# Nomenclature

Sequencer: The program, in python, run on Raspberry Pi. It passes sequences to the arduino.

User Gui: A web interface for the user to interact with the Sequencer. Accessing the Sequencer over http. (not implimented yet)

Circulation Module: A single Arduino that controls a single circulation loop.

LEM: A single Arduino that controls a single LEM.

Module Config: The specifc configuration of a single Circulation Module. Which sensors are connected, and their addresses. The physical pins used for IO.
LEM Config: The specific configuration of a single LEM. Which Circulation Modules are connected, which Reagents are where.

Interval: A single time period, normally 1 second. An ardunio will divide its interval into tasks, and perform them sequentially. (e.g. read sensors, send data, read commands, set outputs, etc.)

State. A state defines the valves, control loops enabled, setpoints and transition conditions for that state.

Sequence. A sequence is a list of states.

Control Loop. A control loop is a function that can be flagged to run in a state. Some control outputs (e.g. PID Circ Pump).

Transition Function. A special form of control loop. It has inputs which will be matched against setpoints. Output is to request a transition to a new state.

Request. A packet from an arduino to the sequencer, not containing process data. (e.g. config, state, etc.)

Dispatch. A packet from the sequencer to an arduino. 

Report. A packet from an arduino to the sequencer, containing data.

NULL state. A state that has no valves activated, and no control loops enabled.




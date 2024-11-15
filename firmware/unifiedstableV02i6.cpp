//######################################################## LIBRARIES ###########################################################################
//##############################################################################################################################################

#include <Wire.h>
#include <PID_v1.h>



//######################################################## CONFIG ######################################k#######################################
//#############################################################################################################################################

//                                       REMEMBER TO CHANGE THE MODUID FOR EACH ARDUINO

                                                   const int modUID=2501;              
                  
//                                       Then label it, and put it on the spreadsheet.  

const double PCBAUDRATE=115200;              // baud rate for PC communication
const int FLOWADDRESS=0x40;                  // wire address for flow sensor
const int PRESSUREADDRESS=0x28;              // wire address for pressure sensor
const unsigned long NUMBEROFUSINAMINUTE=60000000;  // parameter for pump speed calculation. microseconds in a minute, i dont expect this to change.
const int OXYCONFIGPARAMETER=47;             // parameter for pyroscience coms, see their documentation.
const unsigned long FULLINTERVAL = 2000;               // interval for full task list in ms
float SCALE_FACTOR_FLOW = 500.0;       // scale factor for flow rate measurement
float SCALE_FACTOR_TEMP = 200.0;       // scale factor for temperature measurement
const int OXYPIDMINOUTPUT = 200;             // minimum output for oxy PID
const unsigned long PUMPBASEINTERVAL = 3000;           // base interval for pump stepping (ms) this defined the dispense rate for an LEM


//######################################################## VARIABLES + STRUCTS ####################################################################
//#################################################################################################################################################

struct COMMAND_IDS{
    static const int MODSTATEREQUEST=1001;
    static const int PCSTATEDISPATCH=1002;
    static const int MODSTATEREPLY=1003;
    static const int MODDATAREPORT=1515;
    static const int CIRCADDITIONREQUEST = 2004;
};  
/*--------------------------Command IDs Table-------------------------
| Constant                | Value | Description |
|-------------------------|-------|-------------|
| MODSTATEREQUEST         | 1001  | Circulation Module>PC or Liquid Exchange Module>PC. Request for state data |
| PCSTATEDISPATCH         | 1002  | PC>Circulation Module or PC>Liquid Exchange Module. Dispatch of state data, a single row from XXXX_sequence.csv |
| MODSTATEREPLY           | 1003  | Circulation Module>PC or Liquid Exchange Module>PC. A mirror of the state data, to confirm receipt |
| MODDATAREPORT           | 1515  | Circulation Module>PC or Liquid Exchange Module>PC. Report of data, sent at regular intervals |
| CIRCADDITIONREQUEST     | 2004  | Circulation Module>PC. Request for liquid addition |
*/

struct C1001_STATEREQ_POS {
    static const int NULLLEADER = 0;
    static const int MODUID = 1;
    static const int COMMAND = 2;
    static const int STATEID = 3;
    static const int NULLTRAILER = 4;
};

struct C1002_STATE_POS { 
    static const int NULLLEADER=0;
    static const int MODID=1;
    static const int COMMAND=2;
    static const int STATEID=3;
    static const int CIRCFLOW=4;
    static const int PRESSUREFLOW=5;
    static const int VALVE1=6;
    static const int VALVE2=7;
    static const int VALVE3=8;
    static const int VALVE4=9;
    static const int VALVE5=10;
    static const int VALVE6=11;
    static const int VALVE7=12;
    static const int VALVE8=13;
    static const int VALVE9=14;
    static const int VALVE10=15;
    static const int VALVE11=16;
    static const int VALVE12=17;
    static const int VALVE13=18;
    static const int VALVE14=19;
    static const int VALVE15=20;
    static const int VALVE16=21;
    static const int TRANSTIMEFLAG=22;
    static const int TRANSTIMESP=23;
    static const int PRESSURESP=24;
    static const int OXYSP=25;
    static const int PRESINTERVAL=26;
    static const int FLOWINTERVAL=27;
    static const int OXYINTERVAL=28;
    static const int REPORTINTERVAL=29;
    static const int OXYTEMP=30;
    static const int OXYCIRCCHANNEL=31;
    static const int PUMPSPEEDRATIO=32;
    static const int CIRCPUMPCAL=33;
    static const int PRESSUREPUMPCAL=34;
    static const int PRESSUREKP=35;
    static const int PRESSUREKI=36;
    static const int PRESSUREKD=37;
    static const int OXYKP=38;
    static const int OXYKI=39;
    static const int OXYKD=40;
    static const int FLOWINSTALLED=41;
    static const int PRESSUREINSTALLED=42;
    static const int OXYINSTALLED=43;
    static const int ACTIVEOXYCHANNEL1=44;
    static const int ACTIVEOXYCHANNEL2=45;
    static const int ACTIVEOXYCHANNEL3=46;
    static const int ACTIVEOXYCHANNEL4=47;
    static const int PUMP1CW=48;
    static const int PUMP2CW=49;
    static const int PUMP3CW=50;
    static const int PUMP4CW=51;
    static const int PUMP1DIRPIN=52;
    static const int PUMP1STEPPIN=53;
    static const int PUMP2DIRPIN=54;
    static const int PUMP2STEPPIN=55;
    static const int PUMP3DIRPIN=56;
    static const int PUMP3STEPPIN=57;
    static const int PUMP4DIRPIN=58;
    static const int PUMP4STEPPIN=59;
    static const int VALVE1PIN=60;
    static const int VALVE2PIN=61;
    static const int VALVE3PIN=62;
    static const int VALVE4PIN=63;
    static const int VALVE5PIN=64;
    static const int VALVE6PIN=65;
    static const int VALVE7PIN=66;
    static const int VALVE8PIN=67;
    static const int VALVE9PIN=68;
    static const int VALVE10PIN=69;
    static const int VALVE11PIN=70;
    static const int VALVE12PIN=71;
    static const int VALVE13PIN=72;
    static const int VALVE14PIN=73;
    static const int VALVE15PIN=74;
    static const int VALVE16PIN=75;
    static const int OXYCONFIGPARAMETER=76;
    static const int PRESSURE0ADDRESS=77;
    static const int PRESSURECHANNEL=78;
    static const int FLOW0ADDRESS=79;
    static const int DISPENSEPARA=80;
    static const int DISPENSEVOLUMESP=81;
    static const int PCBAUDRATE=82;
    static const int OXYBAUDRATE=83;
    static const int PRESSUREBAUDRATE=84;
    static const int FLAGCHECK=85;
    static const int NULLTRAILER=86;
};

struct C1515_REPORT_POS {
    static const int NULLLEADER = 0;
    static const int MODUID = 1;
    static const int COMMAND = 2;
    .static const int STATEID = 3;
    static const int STATEID = 4;
    static const int OXYMEASURED = 5;
    static const int PRESSUREMEASURED = 6;
    static const int FLOWMEASURED = 7;
    static const int TEMPMEASURED = 8;
    static const int CIRCPUMPSPEED = 9;
    static const int PRESSUREPUMPSPEED = 10;
    static const int PRESSUREPID =11;
    static const int PRESSURESETPOINT =12;
    static const int PRESSUREKP =13;
    static const int PRESSUREKI =14;
    static const int PRESSUREKD =15;
    static const int OXYGENPID = 16;
    static const int OXYGENSETPOINT = 17;
    //static const int OXYGENKP = 17;
    static const int OXYGENKI = 18;
    static const int OXYGENKD = 19;
    static const int OXYGENMEASURED1 = 20;
    static const int OXYGENMEASURED2 = 21;
    static const int OXYGENMEASURED3 = 22;
    static const int OXYGENMEASURED4 = 23;
    static const int NULLTRAILER = 24;
};
/*-------------------------Report Variables Table-------------------------

| Index | Constant               | Variable                          |
|-------|------------------------|-----------------------------------|
| 0     | C1515_REPORT_POS::NULLLEADER      | 0                                 |
| 1     | C1515_REPORT_POS::MODUID          | modUID                            |
| 2     | C1515_REPORT_POS::COMMAND         | COMMAND_IDS::MODDATAREPORT        |
| 3     | C1515_REPORT_POS::STATEID         | state.stateID                     |
| 4     | C1515_REPORT_POS::OXYMEASURED     | measurementData.oxyMeasured       |
| 5     | C1515_REPORT_POS::PRESSUREMEASURED| measurementData.pressureMeasured  |
| 6     | C1515_REPORT_POS::TEMPMEASURED    | communicationData.flow0ScaledTempValue |
| 7     | C1515_REPORT_POS::FLOWMEASURED    | communicationData.flow0ScaledValue|
| 8     | C1515_REPORT_POS::CIRCPUMPSPEED   | circPump.speed                    |
| 9     | C1515_REPORT_POS::PRESSUREPUMPSPEED| pressurePump.speed               |
| 10    | C1515_REPORT_POS::PRESSUREPID     | state.pressureFlow                |
| 11    | C1515_REPORT_POS::PRESSURESETPOINT| state.pressureSP                  |
| 12    | C1515_REPORT_POS::PRESSUREKP      | state.pressureKp                  |
| 13    | C1515_REPORT_POS::PRESSUREKI      | state.pressureKi                  |
| 14    | C1515_REPORT_POS::PRESSUREKD      | state.pressureKd                  |
| 15    | C1515_REPORT_POS::OXYGENPID       | state.circFlow                    |
| 16    | C1515_REPORT_POS::OXYGENSETPOINT  | state.oxySP                       |
| 17    | C1515_REPORT_POS::OXYGENKP        | state.oxyKp                       |
| 18    | C1515_REPORT_POS::OXYGENKI        | state.oxyKi                       |
| 19    | C1515_REPORT_POS::OXYGENKD        | state.oxyKd                       |
| 20    | C1515_REPORT_POS::OXYGENMEASURED1 | oxyChannel1.umolar                |
| 21    | C1515_REPORT_POS::OXYGENMEASURED2 | oxyChannel2.umolar                |
| 22    | C1515_REPORT_POS::OXYGENMEASURED3 | oxyChannel3.umolar                |
| 23    | C1515_REPORT_POS::OXYGENMEASURED4 | oxyChannel4.umolar                |
| 24    | C1515_REPORT_POS::NULLTRAILER     | 0                                 |
*/

struct TASK_NUMBERS{
    static const int OXYWTM1=1;
    static const int OXYWTM2=2;
    static const int OXYWTM3=3;
    static const int OXYWTM4=4;
    static const int FLOW=5;
    static const int PRESSURE=6;
    static const int OXYMEA1=7;
    static const int OXYMEA2=8;
    static const int OXYMEA3=9;
    static const int OXYMEA4=10;
    static const int REPORT=15;
    static const int NULLTASK=0;
};

struct TRANSITION_IDS{
    static const int TIME=46;
    static const int OXYGEN=47;
    static const int PRESSURE=48;
    static const int TEMPERATURE=49;
    static const int MODWAKE=50;
    static const int VOLUME=51;
    static const int LIQUIDADDITION=52;
};

struct FLOW_COMMANDS {
    static const int CMD_START_MEASUREMENT_H2O1 = 0x36;
    static const int CMD_START_MEASUREMENT_H2O2 = 0x08;
    static const int CMD_START_MEASUREMENT_IPA = 0x3615;
    static const int CMD_STOP_MEASUREMENT1 = 0x3F;
    static const int CMD_STOP_MEASUREMENT2 = 0xF9;
    static const int CMD_SOFT_RESET = 0x0006; 
};

struct PYRO_MEA_POS {
    static const int STATUS = 4;
    static const int DPHI = 5;
    static const int UMOLAR = 6;
    static const int MBAR = 7;
    static const int AIRSAT = 8;
    static const int TEMPSAMPLE = 9;
    static const int TEMPCASE = 10;
    static const int SIGNALINTENSITY = 11;
    static const int AMBIENTLIGHT = 12;
    static const int PRESSURE = 13;
    static const int HUMIDITY = 14;
    static const int RESISTORTEMP = 15;
    static const int PERCENTO2 = 16;
    static const int TEMPOPTICAL = 17;
    static const int PH = 18;
    static const int R = 19;
};

struct PYRO_RMR_POS{
    static const int COMMAND = 0;
    static const int CHANNEL = 1;
    static const int BLOCK = 2;
    static const int STARTREG = 3;
    static const int NUMREG = 4;
    static const int READVALUE1 = 5;
    static const int READVALUE2 = 6;
    static const int READVALUE3 = 7;
    static const int READVALUE4 = 8;
    static const int READVALUE5 = 9;
};

struct PYRO_WTM_POS{
    static const int COMMAND = 0;
    static const int CHANNEL = 1;
    static const int BLOCK = 2;
    static const int STARTREG = 3;
    static const int NUMREG = 4;
    static const int WRITEVALUE1 = 5;
    static const int WRITEVALUE2 = 6;
    static const int WRITEVALUE3 = 7;
    static const int WRITEVALUE4 = 8;
    static const int WRITEVALUE5 = 9;
};

struct SENSIRION_FACTORS{
    static const int SLF3S_1300F_TEMP_FACTOR = 200;
    static const int SLF3S_1300F_FLOW_FACTOR = 500;
    static const int SLF3S_4000B_TEMP_FACTOR = 200;
    static const int SLF3S_4000B_FLOW_FACTOR = 32;
};


struct STATE {
    int nullLeader = 0;
    int modId = 0;
    int command = 0;
    int stateId = 0;
    double circFlow = 0;
    double pressureFlow = 0;
    bool valve1 = 0;
    bool valve2 = 0;
    bool valve3 = 0;
    bool valve4 = 0;
    bool valve5 = 0;
    bool valve6 = 0;
    bool valve7 = 0;
    bool valve8 = 0;
    bool valve9 = 0;
    bool valve10 = 0;
    bool valve11 = 0;
    bool valve12 = 0;
    bool valve13 = 0;
    bool valve14 = 0;
    bool valve15 = 0;
    bool valve16 = 0;
    bool transTimeFlag = 0;
    long transTimeSp = 0;
    double pressureSP = 0;
    double oxySP = 0;
    double presInterval = 0;
    double flowInterval = 0;
    double oxyInterval = 0;
    double reportInterval = 0;
    float oxyTemp = 0;
    int oxyCircChannel = 0;
    float pumpSpeedRatio = 0;
    float circPumpCal = 0;
    float pressurePumpCal = 0;
    double pressureKp = 0;
    double pressureKi = 0;
    double pressureKd = 0;
    double oxyKp = 0;
    double oxyKi = 0;
    double oxyKd = 0;
    int flowInstalled = 0;
    int pressureInstalled = 0;
    int oxyInstalled = 0;
    int activeOxyChannel1 = 0;
    int activeOxyChannel2 = 0;
    int activeOxyChannel3 = 0;
    int activeOxyChannel4 = 0;
    bool pump1Cw = 0;
    bool pump2Cw = 0;
    bool pump3Cw = 0;
    bool pump4Cw = 0;
    int pump1DirPin = 0;
    int pump1StepPin = 0;
    int pump2DirPin = 0;
    int pump2StepPin = 0;
    int pump3DirPin = 0;
    int pump3StepPin = 0;
    int pump4DirPin = 0;
    int pump4StepPin = 0;
    int valve1Pin = 0;
    int valve2Pin = 0;
    int valve3Pin = 0;
    int valve4Pin = 0;
    int valve5Pin = 0;
    int valve6Pin = 0;
    int valve7Pin = 0;
    int valve8Pin = 0;
    int valve9Pin = 0;
    int valve10Pin = 0;
    int valve11Pin = 0;
    int valve12Pin = 0;
    int valve13Pin = 0;
    int valve14Pin = 0;
    int valve15Pin = 0;
    int valve16Pin = 0;
    int oxyConfigParameter = 0;
    int pressure0Address = 0;
    int pressureChannel = 0;
    int flow0Address = 0;
    int dispensePara = 0;
    int dispenseVolumeSP = 0;
    long pcBaudRate = 0;
    long oxyBaudRate = 0;
    long pressureBaudRate = 0;
    int flagCheck = 0;
    int nullTrailer = 0;
};

struct TIMINGS {
    unsigned long lastOxy1=0;
    unsigned long lastOxy2=0;
    unsigned long lastOxy3=0;
    unsigned long lastOxy4=0;
    unsigned long lastFlow=0;
    unsigned long lastPres=0;
    unsigned long lastReport=0;
    unsigned long currentTime = 0;
    unsigned long lastTransTime = 0; 
    unsigned long presInterval = 0;
    unsigned long flowInterval = 0;
    unsigned long oxyInterval = 0;
    unsigned long reportInterval = 0;
    unsigned long fullInterval = 0;
};

struct MEASUREMENTDATA{
    double oxyMeasured = 0; 
    double pressureMeasured = 0; 
    double tempMeasured = 0;
    double dispensedVolume =0;
    double volumeSp = 0;
    double tempCorrection=0;
};

struct COMMUNICATIONDATA{
    int i2cReturn = 0;
    uint16_t flow0RawValue = 0; //i2c flow sensor raw value
    int16_t flow0SignedValue = 0; //i2c flow sensor signed value
    float flow0ScaledValue = 0.0f; //i2c flow sensor scaled value
    uint8_t flow0CRC = 0; //i2c flow sensor CRC
    uint16_t flow0Temperature = 0; //i2c flow sensor temperature
    int16_t flow0SignedTempValue = 0; //i2c flow sensor signed temperature value
    float flow0ScaledTempValue = 0.0f; //i2c flow sensor scaled temperature value
    uint8_t flow0TempCRC = 0; //i2c flow sensor temperature CRC
    uint16_t flow0Aux = 0; //i2c flow sensor signaling flags
    uint8_t flow0AuxCRC = 0; //i2c flow sensor auxiliary CRC
    int i2cChannel = 0;
    uint16_t pressureRawSensorValue = 0;
    int16_t pressureSignedSensorValue = 0;
    char stringSerial0[300]=""; // string to hold incoming data from PC
    char stringSerial0command[12]=""; // for command control
    char stringSerial1[300]=""; // string to hold incoming data from DO sensor
    char stringSerial1command[3]=""; // for command control
    bool stringSerial0Complete = false; // flag to show that the incoming string is complete
    bool stringSerial1Complete = false; // flag to show that the incoming string is complete
    int stringSerial0Index = 0; // index for the incoming string
    int stringSerial1Index = 0; // index for the incoming string  
    int nextOxyMeasurementChannel = 0; // the next channel to be measured
    bool stateRequestSent=false; // flag to show that the state request has been sent
    int transType = 0; // the type of transition
    int oxyMeasureType = 0; // the type of DO measurement
    bool pressurestarted = false; // flag to show that the pressure measurement has started
};

struct TASKDATA{
    int numtasks=0;
    unsigned long taskInterval=200;
    int currentTask=0;
    unsigned long lastTaskTime=200;
    int taskNumber = 0;
    int taskList[17] = {0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0}; 
};

struct PUMPCONFIG{
    unsigned long stepInterval=PUMPBASEINTERVAL; 
    unsigned long lastStep;
    double speed=0;
    long maxSpeed =1000000;
    double minOutput = 0;
    double maxOutput = 1000000;
    double volume;
};

struct OXYCHANNEL {
    float oxyMeasured = 0.0f;
    float dphi = 0.0f;
    int status = 0;
    float umolar = 0.0f;
    float mbar = 0.0f;
    float airSat = 0.0f;
    float tempSample = 0.0f;
    float tempCase = 0.0f;
    float signalIntensity = 0.0f;
    float ambientLight = 0.0f;
    float pressure = 0.0f;
    float humidity = 0.0f;
    float resistorTemp = 0.0f;
    float percentO2 = 0.0f;
    float tempOptical = 0.0f;
    float ph = 0.0f;
    float R = 0.0f;
};

//######################################################## INITS ###############################################################
//##############################################################################################################################

STATE state;
MEASUREMENTDATA measurementData;
COMMUNICATIONDATA communicationData;
TASKDATA taskData;
TIMINGS timings;

PUMPCONFIG circPump;
PUMPCONFIG pressurePump;
PUMPCONFIG reagentPump1;
PUMPCONFIG reagentPump2;
PUMPCONFIG reagentPump3;
PUMPCONFIG reagentPump4;
OXYCHANNEL oxyChannel1;
OXYCHANNEL oxyChannel2;
OXYCHANNEL oxyChannel3;
OXYCHANNEL oxyChannel4;

PID oxyPID(&measurementData.oxyMeasured, &circPump.speed, &state.oxySP, state.oxyKp, state.oxyKi, state.oxyKd, DIRECT);
PID pressurePID(&measurementData.pressureMeasured, &pressurePump.speed, &state.pressureSP, state.pressureKp, state.pressureKi, state.pressureKd, REVERSE);

//######################################################## MOD<>PC COM FUNCTIONS ####################################################
//###################################################################################################################################

void commandControl() {
                parseStateData();
    /*strncpy(communicationData.stringSerial0command, communicationData.stringSerial0, 12); // copy the string to a char array
    char* token = strtok(communicationData.stringSerial0command, ",");
    int i = 0;
    while (i < C1002_STATE_POS::COMMAND){
        token = strtok(NULL, ",");
        i++;
    }
    int command = atoi(token);
    //Serial.print("command: ");
    //Serial.println(command);
    switch (command) {
        case COMMAND_IDS::MODSTATEREQUEST:
            break;
        case COMMAND_IDS::PCSTATEDISPATCH:
            parseStateData();
            break;
        case COMMAND_IDS::MODSTATEREPLY:
            break;
        case COMMAND_IDS::MODDATAREPORT:
            break;
        case COMMAND_IDS::CIRCADDITIONREQUEST:
            break;
        default:
            break;*/

}

void parseStateData() {
        Serial.println(communicationData.stringSerial0);
    char* token = strtok(communicationData.stringSerial0, ",");

    int i = 0;
    while (token != NULL) {
        //realtime();
        switch (i) {        
case C1002_STATE_POS::NULLLEADER:   state.nullLeader = atoi(token);     break;
case C1002_STATE_POS::MODID:   state.modId = atoi(token);     break;
case C1002_STATE_POS::COMMAND:   state.command = atoi(token);     break;
case C1002_STATE_POS::STATEID:   state.stateId = atoi(token);     break;
case C1002_STATE_POS::CIRCFLOW:   state.circFlow = atof(token);     break;
case C1002_STATE_POS::PRESSUREFLOW:   state.pressureFlow = atof(token);     break;
case C1002_STATE_POS::VALVE1:   state.valve1 = atoi(token);     break;
case C1002_STATE_POS::VALVE2:   state.valve2 = atoi(token);     break;
case C1002_STATE_POS::VALVE3:   state.valve3 = atoi(token);     break;
case C1002_STATE_POS::VALVE4:   state.valve4 = atoi(token);     break;
case C1002_STATE_POS::VALVE5:   state.valve5 = atoi(token);     break;
case C1002_STATE_POS::VALVE6:   state.valve6 = atoi(token);     break;
case C1002_STATE_POS::VALVE7:   state.valve7 = atoi(token);     break;
case C1002_STATE_POS::VALVE8:   state.valve8 = atoi(token);     break;
case C1002_STATE_POS::VALVE9:   state.valve9 = atoi(token);     break;
case C1002_STATE_POS::VALVE10:   state.valve10 = atoi(token);     break;
case C1002_STATE_POS::VALVE11:   state.valve11 = atoi(token);     break;
case C1002_STATE_POS::VALVE12:   state.valve12 = atoi(token);     break;
case C1002_STATE_POS::VALVE13:   state.valve13 = atoi(token);     break;
case C1002_STATE_POS::VALVE14:   state.valve14 = atoi(token);     break;
case C1002_STATE_POS::VALVE15:   state.valve15 = atoi(token);     break;
case C1002_STATE_POS::VALVE16:   state.valve16 = atoi(token);     break;
case C1002_STATE_POS::TRANSTIMEFLAG:   state.transTimeFlag = atoi(token);     break;
case C1002_STATE_POS::TRANSTIMESP:   state.transTimeSp = atol(token);     break;
case C1002_STATE_POS::PRESSURESP:   state.pressureSP = atof(token);     break;
case C1002_STATE_POS::OXYSP:   state.oxySP = atof(token);     break;
case C1002_STATE_POS::PRESINTERVAL:   state.presInterval = atof(token);     break;
case C1002_STATE_POS::FLOWINTERVAL:   state.flowInterval = atof(token);     break;
case C1002_STATE_POS::OXYINTERVAL:   state.oxyInterval = atof(token);     break;
case C1002_STATE_POS::REPORTINTERVAL:   state.reportInterval = atof(token);     break;
case C1002_STATE_POS::OXYTEMP:   state.oxyTemp = atof(token);     break;
case C1002_STATE_POS::OXYCIRCCHANNEL:   state.oxyCircChannel = atoi(token);     break;
case C1002_STATE_POS::PUMPSPEEDRATIO:   state.pumpSpeedRatio = atof(token);     break;
case C1002_STATE_POS::CIRCPUMPCAL:   state.circPumpCal = atof(token);     break;
case C1002_STATE_POS::PRESSUREPUMPCAL:   state.pressurePumpCal = atof(token);     break;
case C1002_STATE_POS::PRESSUREKP:   state.pressureKp = atof(token);     break;
case C1002_STATE_POS::PRESSUREKI:   state.pressureKi = atof(token);     break;
case C1002_STATE_POS::PRESSUREKD:   state.pressureKd = atof(token);     break;
case C1002_STATE_POS::OXYKP:   state.oxyKp = atof(token);     break;
case C1002_STATE_POS::OXYKI:   state.oxyKi = atof(token);     break;
case C1002_STATE_POS::OXYKD:   state.oxyKd = atof(token);     break;
case C1002_STATE_POS::FLOWINSTALLED:   state.flowInstalled = atoi(token);     break;
case C1002_STATE_POS::PRESSUREINSTALLED:   state.pressureInstalled = atoi(token);     break;
case C1002_STATE_POS::OXYINSTALLED:   state.oxyInstalled = atoi(token);     break;
case C1002_STATE_POS::ACTIVEOXYCHANNEL1:   state.activeOxyChannel1 = atoi(token);     break;
case C1002_STATE_POS::ACTIVEOXYCHANNEL2:   state.activeOxyChannel2 = atoi(token);     break;
case C1002_STATE_POS::ACTIVEOXYCHANNEL3:   state.activeOxyChannel3 = atoi(token);     break;
case C1002_STATE_POS::ACTIVEOXYCHANNEL4:   state.activeOxyChannel4 = atoi(token);     break;
case C1002_STATE_POS::PUMP1CW:   state.pump1Cw = atoi(token);     break;
case C1002_STATE_POS::PUMP2CW:   state.pump2Cw = atoi(token);     break;
case C1002_STATE_POS::PUMP3CW:   state.pump3Cw = atoi(token);     break;
case C1002_STATE_POS::PUMP4CW:   state.pump4Cw = atoi(token);     break;
case C1002_STATE_POS::PUMP1DIRPIN:   state.pump1DirPin = atoi(token);     break;
case C1002_STATE_POS::PUMP1STEPPIN:   state.pump1StepPin = atoi(token);     break;
case C1002_STATE_POS::PUMP2DIRPIN:   state.pump2DirPin = atoi(token);     break;
case C1002_STATE_POS::PUMP2STEPPIN:   state.pump2StepPin = atoi(token);     break;
case C1002_STATE_POS::PUMP3DIRPIN:   state.pump3DirPin = atoi(token);     break;
case C1002_STATE_POS::PUMP3STEPPIN:   state.pump3StepPin = atoi(token);     break;
case C1002_STATE_POS::PUMP4DIRPIN:   state.pump4DirPin = atoi(token);     break;
case C1002_STATE_POS::PUMP4STEPPIN:   state.pump4StepPin = atoi(token);     break;
case C1002_STATE_POS::VALVE1PIN:   state.valve1Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE2PIN:   state.valve2Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE3PIN:   state.valve3Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE4PIN:   state.valve4Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE5PIN:   state.valve5Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE6PIN:   state.valve6Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE7PIN:   state.valve7Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE8PIN:   state.valve8Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE9PIN:   state.valve9Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE10PIN:   state.valve10Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE11PIN:   state.valve11Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE12PIN:   state.valve12Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE13PIN:   state.valve13Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE14PIN:   state.valve14Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE15PIN:   state.valve15Pin = atoi(token);     break;
case C1002_STATE_POS::VALVE16PIN:   state.valve16Pin = atoi(token);     break;
case C1002_STATE_POS::OXYCONFIGPARAMETER:   state.oxyConfigParameter = atoi(token);     break;
case C1002_STATE_POS::PRESSURE0ADDRESS:   state.pressure0Address = atoi(token);     break;
case C1002_STATE_POS::PRESSURECHANNEL:   state.pressureChannel = atoi(token);     break;
case C1002_STATE_POS::FLOW0ADDRESS:   state.flow0Address = atoi(token);     break;
case C1002_STATE_POS::DISPENSEPARA:   state.dispensePara = atoi(token);     break;
case C1002_STATE_POS::DISPENSEVOLUMESP:   state.dispenseVolumeSP = atoi(token);     break;
case C1002_STATE_POS::PCBAUDRATE:   state.pcBaudRate = atol(token);     break;
case C1002_STATE_POS::OXYBAUDRATE:   state.oxyBaudRate = atol(token);     break;
case C1002_STATE_POS::PRESSUREBAUDRATE:   state.pressureBaudRate = atol(token);     break;
case C1002_STATE_POS::FLAGCHECK:   state.flagCheck = atoi(token);     break;
case C1002_STATE_POS::NULLTRAILER:   state.nullTrailer = atoi(token);     break;
                    }
        token = strtok(NULL, ",");
        i++;
    }
    communicationData.stringSerial0Index = 0;
    communicationData.stringSerial0[0] = '\0';
    communicationData.stringSerial0Complete = false;
    communicationData.stateRequestSent = false;

    newStateCleanup();
}

void newStateCleanup(){
    updateTaskList();
    microIntervals();
    if (state.oxyInstalled == 1) {
        Serial1.begin(state.oxyBaudRate);
    }
    flowSensorSetup();
    flowStart();
    setValves();
}

void flowSensorSetup() {
     if (state.flowInstalled == 2 || state.flowInstalled == 4000) {
        SCALE_FACTOR_FLOW = SENSIRION_FACTORS::SLF3S_4000B_FLOW_FACTOR;
        SCALE_FACTOR_TEMP = SENSIRION_FACTORS::SLF3S_4000B_TEMP_FACTOR;
    }
    else {        
        SCALE_FACTOR_FLOW = SENSIRION_FACTORS::SLF3S_1300F_FLOW_FACTOR;
        SCALE_FACTOR_TEMP = SENSIRION_FACTORS::SLF3S_1300F_TEMP_FACTOR;
        }
}

void microIntervals(){
    timings.presInterval = state.presInterval * 1000;
    timings.flowInterval = state.flowInterval * 1000;
    timings.oxyInterval = state.oxyInterval * 1000;
    timings.reportInterval = state.reportInterval * 1000;
    timings.fullInterval = FULLINTERVAL * 1000;
    state.transTimeSp= state.transTimeSp * 1000;
}


void formatValueToBuffer(double value, char* buffer, size_t bufferSize) {
    if (value == static_cast<int>(value)) {
        // Value is an integer
        snprintf(buffer, bufferSize, "%d,", static_cast<int>(value));
    } else {
        // Value is a float, using snprintf directly
        snprintf(buffer, bufferSize, "%.2f,", value);
    }
}

void moduleDataReport(){
    char buffer[32]; 
    for (int i = C1515_REPORT_POS::NULLLEADER; i <= C1515_REPORT_POS::NULLTRAILER; i++) {
        realtime();
        double value = 0.0;
        switch (i) {
            case C1515_REPORT_POS::NULLLEADER: value = 0; break;
            case C1515_REPORT_POS::MODUID: value = modUID; break;
            case C1515_REPORT_POS::COMMAND: value = COMMAND_IDS::MODDATAREPORT; break;
            case C1515_REPORT_POS::STATEID: value = state.stateId; break;
            case C1515_REPORT_POS::OXYMEASURED: value= measurementData.oxyMeasured; break;
            case C1515_REPORT_POS::PRESSUREMEASURED: value = measurementData.pressureMeasured; break;
            case C1515_REPORT_POS::TEMPMEASURED: value = communicationData.flow0ScaledTempValue; break;
            case C1515_REPORT_POS::FLOWMEASURED: value = communicationData.flow0ScaledValue; break;
            case C1515_REPORT_POS::CIRCPUMPSPEED: value = circPump.speed; break;
            case C1515_REPORT_POS::PRESSUREPUMPSPEED: value = pressurePump.speed; break;
            case C1515_REPORT_POS::PRESSURESETPOINT: value = state.pressureSP; break;
            case C1515_REPORT_POS::PRESSUREKP: value = state.pressureKp; break;
            case C1515_REPORT_POS::PRESSUREKI: value = state.pressureKi; break;
            case C1515_REPORT_POS::PRESSUREKD: value = state.pressureKd; break;
            case C1515_REPORT_POS::OXYGENSETPOINT: value = state.oxySP; break;
            case C1515_REPORT_POS::OXYGENKP: value = state.oxyKp; break;
            case C1515_REPORT_POS::OXYGENKI: value = state.oxyKi; break;
            case C1515_REPORT_POS::OXYGENKD: value = state.oxyKd; break;
            case C1515_REPORT_POS::OXYGENMEASURED1: value = oxyChannel1.oxyMeasured; break;
            case C1515_REPORT_POS::OXYGENMEASURED2: value = oxyChannel2.oxyMeasured; break;
            case C1515_REPORT_POS::OXYGENMEASURED3: value = oxyChannel3.oxyMeasured; break;
            case C1515_REPORT_POS::OXYGENMEASURED4: value = oxyChannel4.oxyMeasured; break;
            case C1515_REPORT_POS::PRESSUREPID: value = (state.pressureFlow == -1) ? 1 : 0; break;
            case C1515_REPORT_POS::OXYGENPID: value = (state.circFlow == -1) ? 1 : 0; break;
            case C1515_REPORT_POS::NULLTRAILER: value = 0; break;
        }
        // Format value based on its type and write to buffer
        formatValueToBuffer(value, buffer, sizeof(buffer));
        Serial.write(buffer);
    }
    snprintf(buffer, sizeof(buffer), "\n");
    Serial.write(buffer);

}

void requestState(int transId) {
    char buffer[60];
    for (int i = C1001_STATEREQ_POS::NULLLEADER; i <= C1001_STATEREQ_POS::NULLTRAILER; i++) {
        realtime();
        switch (i) {
            case C1001_STATEREQ_POS::NULLLEADER:
                snprintf(buffer, sizeof(buffer), "%d,", 0);
                break;
            case C1001_STATEREQ_POS::MODUID:
                snprintf(buffer, sizeof(buffer), "%d,", modUID);
                break;
            case C1001_STATEREQ_POS::COMMAND:
                snprintf(buffer, sizeof(buffer), "%d,", COMMAND_IDS::MODSTATEREQUEST);
                break;
            case C1001_STATEREQ_POS::STATEID:
                snprintf(buffer, sizeof(buffer), "%d,", transId);
                break;
            case C1001_STATEREQ_POS::NULLTRAILER:
                snprintf(buffer, sizeof(buffer), "%d,\n", 0);
                break;
        }
        Serial.write(buffer);
    }
}

//######################################################## SENSOR FUNCTIONS ############################################################
//######################################################################################################################################

void staggerOxy(){
    int numberofchannels=0;
    if (state.activeOxyChannel1==1){
        numberofchannels++;
    }
    if (state.activeOxyChannel2==1){
        numberofchannels++;
    }
    if (state.activeOxyChannel3==1){
        numberofchannels++;
    }
    if (state.activeOxyChannel4==1){
        numberofchannels++;
    }
    if (numberofchannels==0){
        return;
    }

    timings.lastOxy2=timings.currentTime+(timings.oxyInterval*(1+(1/numberofchannels)));
    timings.lastOxy3=timings.currentTime+(timings.oxyInterval*(1+(2/numberofchannels)));
    timings.lastOxy4=timings.currentTime+(timings.oxyInterval*(1+(3/numberofchannels)));
}



void oxyMeasurement(int channel) {
    char message[20]; 
    snprintf(message, sizeof(message), "MEA %d %d\r", channel, state.oxyConfigParameter);

    Serial1.write(message);

    communicationData.nextOxyMeasurementChannel = channel;
}

void flowMeasurement() {
    Wire.requestFrom(state.flow0Address, 9);
    communicationData.i2cChannel = state.flow0Address;
}
void flowStart() {
    if ((state.flowInstalled != 0) && !communicationData.pressurestarted) {
        Wire.begin();
        int ret = 1;
        int attempts = 0;
        const int maxAttempts = 5; 

        do {
            Wire.requestFrom(state.flow0Address, 9);
            delay(500);
            if (Wire.available() == 9) {
                communicationData.pressurestarted = true; // Move inside the loop to ensure it's only set on success
                break;
            } else {
                Wire.beginTransmission(0x00);
                Wire.write(FLOW_COMMANDS::CMD_SOFT_RESET);
                Wire.endTransmission();
                delay(500);
                Wire.beginTransmission(state.flow0Address);
                Wire.write(FLOW_COMMANDS::CMD_START_MEASUREMENT_H2O1);
                Wire.write(FLOW_COMMANDS::CMD_START_MEASUREMENT_H2O2);
                ret = Wire.endTransmission();
                if (ret != 0) {
                    char errorMsg[] = "Flow Start Signal Error\n";
                    Serial.write(errorMsg, sizeof(errorMsg));
                    delay(500); // Wait long enough for chip reset to complete
                }
                attempts++;
            }
        } while (ret != 0 && attempts < maxAttempts);

        if (attempts >= maxAttempts) {

        }
    }
}

void pressureMeasurement(){
        Wire.beginTransmission(state.pressure0Address);
        Wire.write(0xF1);
        Wire.endTransmission();
        Wire.requestFrom(state.pressure0Address, 2);
}

void pyroCommandControl(){
    parseOxyData();
}

void parseOxyData(){
    char* token = strtok(communicationData.stringSerial1, " ");

    int index = 0;
    OXYCHANNEL* currentChannel = NULL;
    switch (communicationData.nextOxyMeasurementChannel) {
        case 1:
            currentChannel = &oxyChannel1;
            break;
        case 2:
            currentChannel = &oxyChannel2;
            break;
        case 3:
            currentChannel = &oxyChannel3;
            break;
        case 4:
            currentChannel = &oxyChannel4;
            break;
        default:
            // handle error
            break;
    }
    if (strcmp(token, "WTM")==0) {
        communicationData.stringSerial1[0] = '\0';
        communicationData.stringSerial1Index = 0;
        communicationData.stringSerial1Complete = false;
        return;
    }
    while (token != NULL) {
        realtime();
        switch (index) {
            case PYRO_MEA_POS::STATUS:
                currentChannel->status = atoi(token);
                break;
            case PYRO_MEA_POS::DPHI:
                currentChannel->dphi = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::UMOLAR:
                currentChannel->umolar = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::MBAR:
                currentChannel->mbar = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::AIRSAT:
                currentChannel->airSat = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::TEMPSAMPLE:
                currentChannel->tempSample = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::TEMPCASE:
                currentChannel->tempCase = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::SIGNALINTENSITY:
                currentChannel->signalIntensity = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::AMBIENTLIGHT:
                currentChannel->ambientLight = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::PRESSURE:
                currentChannel->pressure = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::HUMIDITY:
                currentChannel->humidity = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::RESISTORTEMP:
                currentChannel->resistorTemp = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::PERCENTO2:
                currentChannel->percentO2 = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::TEMPOPTICAL:
                currentChannel->tempOptical = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::PH:
                currentChannel->ph = atof(token) / 1000.0;
                break;
            case PYRO_MEA_POS::R:
                currentChannel->R = atof(token) / 1000.0;
                break;
        }
        token = strtok(NULL, " ");
        index++;
    }

    switch (communicationData.oxyMeasureType) {
        case PYRO_MEA_POS::STATUS:
            currentChannel->oxyMeasured = currentChannel->status;
            break;
        case PYRO_MEA_POS::DPHI:
            currentChannel->oxyMeasured = currentChannel->dphi;
            break;
        case PYRO_MEA_POS::UMOLAR:
            currentChannel->oxyMeasured = currentChannel->umolar;
            break;
        case PYRO_MEA_POS::MBAR:
            currentChannel->oxyMeasured = currentChannel->mbar;
            break;
        case PYRO_MEA_POS::AIRSAT:
            currentChannel->oxyMeasured = currentChannel->airSat;
            break;
        case PYRO_MEA_POS::TEMPSAMPLE:
            currentChannel->oxyMeasured = currentChannel->tempSample;
            break;
        case PYRO_MEA_POS::TEMPCASE:
            currentChannel->oxyMeasured = currentChannel->tempCase;
            break;
        case PYRO_MEA_POS::SIGNALINTENSITY:
            currentChannel->oxyMeasured = currentChannel->signalIntensity;
            break;
        case PYRO_MEA_POS::AMBIENTLIGHT:
            currentChannel->oxyMeasured = currentChannel->ambientLight;
            break;
        case PYRO_MEA_POS::PRESSURE:
            currentChannel->oxyMeasured = currentChannel->pressure;
            break;
        case PYRO_MEA_POS::HUMIDITY:
            currentChannel->oxyMeasured = currentChannel->humidity;
            break;
        case PYRO_MEA_POS::RESISTORTEMP:
            currentChannel->oxyMeasured = currentChannel->resistorTemp;
            break;
        case PYRO_MEA_POS::PERCENTO2:
            currentChannel->oxyMeasured = currentChannel->percentO2;
            break;
        case PYRO_MEA_POS::TEMPOPTICAL:
            currentChannel->oxyMeasured = currentChannel->tempOptical;
            break;
        case PYRO_MEA_POS::PH:
            currentChannel->oxyMeasured = currentChannel->ph;
            break;
        case PYRO_MEA_POS::R:
            currentChannel->oxyMeasured = currentChannel->R;
            break;
        default:
            // handle error
            break;
    }
    communicationData.stringSerial1[0] = '\0';
    communicationData.stringSerial1Index = 0;
    communicationData.stringSerial1Complete = false;
}

//######################################################## TASK FUNCTIONS ##############################################################
//######################################################################################################################################

/*-------------------------Task Sheduling Note-------------------------
To avoid serial buffer overflow or any other resource scarcity, the interval will be evenly divided, so that each task is fully complete before another is queued.

currentTaskList is used to track the tasks to be completed in the interval, and currentTask is used to track the current task.

When a state is issued to the arduino from the PC, the task list will be updated, and taskInterval will be calculated.

in principle, tasks could be assigned to be completed in any order, but keeping to position-task parity e.g. [0,1,0,0,4,5,0,0,0,0,0,0,0,0,0,15] is best.

TASK ASSIGNMENT LIST (taskKeys, above. The comment list below may be out of date)
current task = 0, null, move immediately to next task
current task = 1, request DO measurement for channel 1
current task = 2, request DO measurement for channel 2
current task = 3, request DO measurement for channel 3
current task = 4, request DO measurement for channel 4
current task = 5, request flow measurement (if i2c, analogue does not req task)
current task = 6, request pressure measurement
current task = 15, compile report and send to PC

FLAG to FUNCTION LIST
FLAG                    FUNCTION            DESCRIPTION
valveChange             setValves()         set valves to desired state
inStringSerial0Complete commandControl()  check if there is complete data on serial0, from the PC. if so, call commandControl()
inStringSerial1Complete parseOxyData()      check if there is complete data on serial1, from the DO sensor. if so, call parseDoData()
Serial.available        serialEvent()       check for serial data from PC
Serial1.available       serialEvent1()      check for serial data from DO sensor
Wire.available          i2cEvent()          check for i2c data from flow or pressure sensor
lastTaskTime            taskControl()            at task time, taskControl will call the appropriate function, update the task list, and set the next task time


CUSTOM TASK INTERVALS
Tasks can be individually controlled by modifying their task interval in XXXX_sequence.csv. e.g. oxyInterval, flowInterval, presInterval, reportInterval.
The assosiated function will not be called if the interval has not elapsed. The interval will be reset when the function is called. (timings.lastOxy1 etc)
*/

void updateTaskList(){
    taskData.numtasks=0;
    if (state.activeOxyChannel1==1){
        taskData.taskList[TASK_NUMBERS::OXYMEA1]=TASK_NUMBERS::OXYMEA1;
        // taskData.taskList[TASK_NUMBERS::OXYWTM1]=TASK_NUMBERS::OXYWTM1;
        taskData.numtasks=taskData.numtasks+1;
    }
    if (state.activeOxyChannel2==1){
        taskData.taskList[TASK_NUMBERS::OXYMEA2]=TASK_NUMBERS::OXYMEA2;
        // taskData.taskList[TASK_NUMBERS::OXYWTM2]=TASK_NUMBERS::OXYWTM2;
        taskData.numtasks=taskData.numtasks+1;
    }
    if (state.activeOxyChannel3==1){
        taskData.taskList[TASK_NUMBERS::OXYMEA3]=TASK_NUMBERS::OXYMEA3;
    //    / taskData.taskList[TASK_NUMBERS::OXYWTM3]=TASK_NUMBERS::OXYWTM3;
        taskData.numtasks=taskData.numtasks+1;
    }
    if (state.activeOxyChannel4==1){
        taskData.taskList[TASK_NUMBERS::OXYMEA4]=TASK_NUMBERS::OXYMEA4;
        // taskData.taskList[TASK_NUMBERS::OXYWTM4]=TASK_NUMBERS::OXYWTM4;
        taskData.numtasks=taskData.numtasks+1;
    }
    if (state.flowInstalled==1){
        taskData.taskList[TASK_NUMBERS::FLOW]=TASK_NUMBERS::FLOW;
        taskData.numtasks=taskData.numtasks+1;
    }
    if (state.pressureInstalled==1){
        Serial.println("Pressure Installed");
        taskData.taskList[TASK_NUMBERS::PRESSURE]=TASK_NUMBERS::PRESSURE;
        taskData.numtasks=taskData.numtasks+1;
    }
    taskData.taskList[TASK_NUMBERS::REPORT]=TASK_NUMBERS::REPORT;
    taskData.numtasks=taskData.numtasks+1;
    taskData.taskNumber=0;
    taskData.currentTask=taskData.taskList[taskData.taskNumber];
    taskData.taskInterval=timings.fullInterval/taskData.numtasks;
    taskData.lastTaskTime=timings.currentTime;
}

void nextTask() {
    if (taskData.currentTask!=0){        
        taskData.lastTaskTime = taskData.lastTaskTime + taskData.taskInterval;
    }
    taskData.taskNumber += 1;
    taskData.currentTask = taskData.taskList[taskData.taskNumber];
    if (taskData.taskNumber == sizeof(taskData.taskList) / sizeof(taskData.taskList[1])) {
        taskData.taskNumber = 0;
        taskData.currentTask = taskData.taskList[taskData.taskNumber]; 
}
}

void taskControl(){
    /*Serial.print("Task Interval: ");
    Serial.print(taskData.taskInterval);
    Serial.print(".  Task Number: ");
    Serial.print(taskData.taskNumber);
    Serial.print(".  Task List: [");
    for (int i=0; i<16; i++){
        Serial.print(taskData.taskList[i]);
        Serial.print(",");
    }
    Serial.print("].  Current Task: ");
    Serial.println(taskData.currentTask);
*/
    switch (taskData.currentTask) {
        case TASK_NUMBERS::NULLTASK:
            nextTask();
            break;
        case TASK_NUMBERS::OXYMEA1:
            if (timings.currentTime - timings.lastOxy1 > timings.oxyInterval) {
                oxyMeasurement(1);
                timings.lastOxy1 = timings.lastOxy1 + timings.oxyInterval;
            }
            nextTask();
            break;
        case TASK_NUMBERS::OXYMEA2:
            if (timings.currentTime - timings.lastOxy2 > timings.oxyInterval) {
                oxyMeasurement(2);
                timings.lastOxy2 = timings.lastOxy2 + timings.oxyInterval;
            }
            nextTask();
            break;
        case TASK_NUMBERS::OXYMEA3:   
            if (timings.currentTime - timings.lastOxy3 > timings.oxyInterval) {
                oxyMeasurement(3);
                timings.lastOxy3 = timings.lastOxy3 + timings.oxyInterval;
            } 
            nextTask();
            break;
        case TASK_NUMBERS::OXYMEA4:
            if (timings.currentTime - timings.lastOxy4 > timings.oxyInterval) {
                oxyMeasurement(4);
                timings.lastOxy4 = timings.lastOxy4 + timings.oxyInterval;
            }
            nextTask();
            break;
        case TASK_NUMBERS::FLOW:
            if (timings.currentTime - timings.lastFlow > timings.flowInterval) {
                flowMeasurement();
                timings.lastFlow = timings.lastFlow + timings.flowInterval;
                }
            nextTask();
            break;
        case TASK_NUMBERS::PRESSURE:
            if (timings.currentTime - timings.lastPres > timings.presInterval) {
                pressureMeasurement();
                timings.lastPres = timings.lastPres + timings.presInterval;
            }
            nextTask();
            break;
        case TASK_NUMBERS::OXYWTM1:
            // oxyTemperature(1);
            nextTask();
            break;
        case TASK_NUMBERS::OXYWTM2:
            // oxyTemperature(2);
            nextTask();
            break;
        case TASK_NUMBERS::OXYWTM3:
            // oxyTemperature(3);
            nextTask();
            break;
        case TASK_NUMBERS::OXYWTM4:
            // oxyTemperature(4);
            nextTask();
            break;
        case TASK_NUMBERS::REPORT:
            if (timings.currentTime - timings.lastReport > timings.reportInterval) {
                moduleDataReport();
                timings.lastReport = timings.lastReport + timings.reportInterval;
            }
            nextTask();
            break;
            }  
    }

//######################################################## PROCESS CONTROL FUNCTIONS ###################################################
//######################################################################################################################################

/*-------------------------Pump Control Note------------------------- 
Modal: use -1 for PID control, 0 for off, or any non-negative value for constant speed

The Oxy Channel used for circulation feedback is set by state.oxyCircChannel from the sequence file.

if you're seeing a lot of "Error: circPumpCal is 0 on Module X" messages, then the state is probably not being set correctly from the sequence file.
*/

void pressureControl() {
    if (state.pressureFlow == -1) {
        pressurePID.SetTunings(state.pressureKp, state.pressureKi, state.pressureKd);
        pressurePID.Compute();
    }
    else if (state.pressureFlow != -1) {
        if (state.pressurePumpCal != 0) {
            pressurePump.speed = state.pressureFlow / state.pressurePumpCal;
        } else {
            char errorMessage[50];
            sprintf(errorMessage, "Error: pressurePumpCal is 0 on Module %d\n", modUID);
            Serial.write(errorMessage, strlen(errorMessage));
            pressurePump.speed = 0;
           }
    }

    pressurePump.maxSpeed = circPump.speed * state.pumpSpeedRatio;
    
    if (pressurePump.speed > pressurePump.maxSpeed) {
        pressurePump.speed = pressurePump.maxSpeed;
    }
    else if (pressurePump.speed < 0) {
        pressurePump.speed = 0;
    }
    if (pressurePump.speed != 0) {
        pressurePump.stepInterval = NUMBEROFUSINAMINUTE / pressurePump.speed;
    }
    else {
        pressurePump.stepInterval = 10000;
        pressurePump.lastStep = timings.currentTime;
    }
}

void oxyCirc() {
        if (state.oxyCircChannel == 1){   
           measurementData.oxyMeasured = oxyChannel1.oxyMeasured;
        }
        else if (state.oxyCircChannel == 2) {
            measurementData.oxyMeasured = oxyChannel2.oxyMeasured;
        } 
        else if (state.oxyCircChannel == 3) {
            measurementData.oxyMeasured = oxyChannel3.oxyMeasured;
        } 
        else if (state.oxyCircChannel == 4) {
            measurementData.oxyMeasured = oxyChannel4.oxyMeasured;
        }

    if (state.circFlow == -1) {
        oxyPID.SetTunings(state.oxyKp, state.oxyKi, state.oxyKd);
        oxyPID.Compute();
    }

    if (state.circFlow != -1) {
        if (state.circPumpCal != 0) {
            circPump.speed = state.circFlow / state.circPumpCal;
        } else {
            char errorMessage[50];
            sprintf(errorMessage, "Error: circPumpCal is 0 on Module %d", modUID);
            Serial.write(errorMessage, strlen(errorMessage));
            circPump.speed = 0;
        }
    }
    if (circPump.speed !=0) {
        if (circPump.speed > circPump.maxSpeed) {
            circPump.speed = circPump.maxSpeed;
        }
        else if (circPump.speed < 0) {
            circPump.speed = 0;
        }
        circPump.stepInterval = NUMBEROFUSINAMINUTE / circPump.speed;
    }
    else {
        circPump.stepInterval = 10000;
        circPump.lastStep = timings.currentTime;
    }
}

void dispenseControl(){
    if (state.dispensePara != 1){
        reagentPump1.lastStep=timings.currentTime;
    }
    if (state.dispensePara != 2){
        reagentPump2.lastStep=timings.currentTime;
    }
    if (state.dispensePara != 3){
        reagentPump3.lastStep=timings.currentTime;
    }
    if (state.dispensePara != 4){
        reagentPump4.lastStep=timings.currentTime;
    } 
}

//######################################################## MAIN FUNCTIONS ##############################################################
//######################################################################################################################################

void realtime(){
    dispenseControl();
    if (timings.currentTime-circPump.lastStep>circPump.stepInterval){
        pumpStep(1);
        circPump.lastStep=circPump.lastStep+circPump.stepInterval;
        }

    if (timings.currentTime-pressurePump.lastStep>pressurePump.stepInterval){
        pumpStep(2);
        pressurePump.lastStep=pressurePump.lastStep+pressurePump.stepInterval;
        }

    if (timings.currentTime-reagentPump1.lastStep>reagentPump1.stepInterval){
        pumpStep(1);
        reagentPump1.lastStep=reagentPump1.lastStep+reagentPump1.stepInterval;
        }
    
    if (timings.currentTime-reagentPump2.lastStep>reagentPump2.stepInterval){
        pumpStep(2);
        reagentPump2.lastStep=reagentPump2.lastStep+reagentPump2.stepInterval;  
        }

    if (timings.currentTime-reagentPump3.lastStep>reagentPump3.stepInterval){
        pumpStep(3);
        reagentPump3.lastStep=reagentPump3.lastStep+reagentPump3.stepInterval;
        }

    if (timings.currentTime-reagentPump4.lastStep>reagentPump4.stepInterval){
        pumpStep(4);
        reagentPump4.lastStep=reagentPump4.lastStep+reagentPump4.stepInterval;
        }
}


void setup(){
    state.pcBaudRate = PCBAUDRATE;
    state.flow0Address = FLOWADDRESS;
    state.oxyConfigParameter = OXYCONFIGPARAMETER;
    state.pressure0Address = PRESSUREADDRESS;
    communicationData.transType = TRANSITION_IDS::MODWAKE;
    communicationData.oxyMeasureType = PYRO_MEA_POS::UMOLAR;
    circPump.minOutput = OXYPIDMINOUTPUT;
    
    Serial.begin(state.pcBaudRate);

    requestState(TRANSITION_IDS::MODWAKE);
        while (communicationData.stringSerial0Complete==false){
            serialEvent();
        }
    commandControl();

    oxyPID.SetMode(AUTOMATIC);
    pressurePID.SetMode(AUTOMATIC);

    pressurePID.SetOutputLimits(pressurePump.minOutput, pressurePump.maxOutput);
    oxyPID.SetOutputLimits(circPump.minOutput, circPump.maxOutput);

    pinMode(state.valve1Pin, OUTPUT);
    pinMode(state.valve2Pin, OUTPUT);
    pinMode(state.valve3Pin, OUTPUT);
    pinMode(state.valve4Pin, OUTPUT);
    pinMode(state.valve5Pin, OUTPUT);
    pinMode(state.valve6Pin, OUTPUT);
    pinMode(state.valve7Pin, OUTPUT);
    pinMode(state.valve8Pin, OUTPUT);
    pinMode(state.valve9Pin, OUTPUT);
    pinMode(state.valve10Pin, OUTPUT);
    pinMode(state.valve11Pin, OUTPUT);
    pinMode(state.valve12Pin, OUTPUT);
    pinMode(state.valve13Pin, OUTPUT);
    pinMode(state.valve14Pin, OUTPUT);
    pinMode(state.valve15Pin, OUTPUT);
    pinMode(state.valve16Pin, OUTPUT);
    pinMode(state.pump1DirPin, OUTPUT);
    pinMode(state.pump1StepPin, OUTPUT);
    pinMode(state.pump2DirPin, OUTPUT);
    pinMode(state.pump2StepPin, OUTPUT);
    pinMode(state.pump3DirPin, OUTPUT);
    pinMode(state.pump3StepPin, OUTPUT);
    pinMode(state.pump4DirPin, OUTPUT);
    pinMode(state.pump4StepPin, OUTPUT);
    pinMode(state.pressure0Address, INPUT);

    if (state.oxyInstalled==1){
        Serial1.begin(state.oxyBaudRate);
        }

    staggerOxy();
    flowStart();
}



void loop(){
    timings.currentTime = micros();
    realtime();
    oxyCirc();
    pressureControl();

    if (state.pressureInstalled==2){        //==2 is for analogue, ==1 is for i2c.
    measurementData.pressureMeasured=analogRead(state.pressure0Address);}

    if (communicationData.stringSerial0Complete){  
        commandControl();}
    
    if (communicationData.stringSerial1Complete){  
        pyroCommandControl();}
    
    if (timings.currentTime-taskData.lastTaskTime>taskData.taskInterval){;
        taskControl();}  
    
    if (Wire.available()){
        i2cEvent();}
    
    if (state.transTimeFlag && !communicationData.stateRequestSent){
        if (timings.currentTime-timings.lastTransTime>state.transTimeSp){
            communicationData.transType=TRANSITION_IDS::TIME;
            requestState(TRANSITION_IDS::TIME);
            communicationData.stateRequestSent=true;
            timings.lastTransTime=timings.currentTime;
    }
    }

// if (state.transOxyFlag){
//     if (measurementData.oxyMeasured>state.transOxySP){
//         communicationData.transType=TRANSITION_IDS::OXYGEN;
//         requestState(TRANSITION_IDS::OXYGEN);
//         timings.lastTransTime=timings.currentTime;
// }
// }

// if (state.transTempFlag){
//     if (measurementData.tempMeasured>state.transTempSP){
//         communicationData.transType=TRANSITION_IDS::TEMPERATURE;
//         requestState(TRANSITION_IDS::TEMPERATURE);
//         timings.lastTransTime=timings.currentTime;
// }
// }

if (state.dispensePara){
    if (measurementData.dispensedVolume>measurementData.volumeSp){
        measurementData.volumeSp=0;
        communicationData.transType=TRANSITION_IDS::VOLUME;
        requestState(TRANSITION_IDS::VOLUME);
        timings.lastTransTime=timings.currentTime;
}
}

if (Serial1.available()) {
    serialEvent1();
}

}
//######################################################## SERIAL COM FUNCTIONS #######################################################
//#####################################################################################################################################

void serialEvent() {
while (Serial.available()) {
    realtime(); 
    char inCharS0 = (char)Serial.read();
    if (inCharS0 == '\n' || inCharS0 == '\r') {
    communicationData.stringSerial0Complete = true;
    communicationData.stringSerial0Index = 0;
    } else {
    communicationData.stringSerial0[communicationData.stringSerial0Index] = inCharS0;
            communicationData.stringSerial0Index++;
                }
}
}


void serialEvent1(){    
while (Serial1.available()) {
    realtime();
    char inCharS1=(char)Serial1.read();
    if (inCharS1 == '\n' || inCharS1 == '\r') {
    communicationData.stringSerial1Complete = true;
    communicationData.stringSerial1Index = 0;
    } else {
    communicationData.stringSerial1[communicationData.stringSerial1Index] = inCharS1;
            communicationData.stringSerial1Index++;
                }
}}


void i2cEvent() {
    if (Wire.available()) {
        if (communicationData.i2cChannel == state.flow0Address) {
            if (Wire.available() < 9) {
                char flowComError[] = "Flow Sensor Communication Error, retrying\n\0";
                Serial.write(flowComError, strlen(flowComError));
                flowMeasurement();
            } else {
                communicationData.flow0RawValue = Wire.read() << 8;
                communicationData.flow0RawValue |= Wire.read(); 
                communicationData.flow0CRC = Wire.read();
                communicationData.flow0Temperature = Wire.read() << 8;
                communicationData.flow0Temperature |= Wire.read(); 
                communicationData.flow0TempCRC = Wire.read();
                communicationData.flow0Aux = Wire.read() << 8; 
                communicationData.flow0Aux |= Wire.read(); 
                communicationData.flow0AuxCRC = Wire.read();

                communicationData.flow0SignedValue = (int16_t)communicationData.flow0RawValue;
                communicationData.flow0ScaledValue = ((float)communicationData.flow0SignedValue) / SCALE_FACTOR_FLOW;

                communicationData.flow0SignedTempValue = (int16_t)communicationData.flow0Temperature;
                communicationData.flow0ScaledTempValue = ((float)communicationData.flow0SignedTempValue) / SCALE_FACTOR_TEMP;
            }}

  
        if (communicationData.i2cChannel == state.pressure0Address) {
            if (Wire.available() < 2) {
                char pressureComError[] = "Pressure Sensor Communication Error, retrying\n\0";
                Serial.write(pressureComError, strlen(pressureComError));
                pressureMeasurement();
            } else {
                communicationData.pressureRawSensorValue = Wire.read() << 8 | Wire.read();
                communicationData.pressureSignedSensorValue = (int16_t)communicationData.pressureRawSensorValue;
            }
        }
    }
}

//######################################################## OUTPUT FUNCTIONS ##########################################################
//####################################################################################################################################

void pumpStep(int pump){
    switch (pump)
    {
    case 1:
        digitalWrite(state.pump1DirPin, state.pump1Cw);
        digitalWrite(state.pump1StepPin, HIGH);
        digitalWrite(state.pump1StepPin, LOW);
        break;
    case 2:
        digitalWrite(state.pump2DirPin, state.pump2Cw);
        digitalWrite(state.pump2StepPin, HIGH);
        digitalWrite(state.pump2StepPin, LOW);
        break;
    case 3:
        digitalWrite(state.pump3DirPin, state.pump3Cw);
        digitalWrite(state.pump3StepPin, HIGH);
        digitalWrite(state.pump3StepPin, LOW);
        break;
    case 4:
        digitalWrite(state.pump4DirPin, state.pump4Cw);
        digitalWrite(state.pump4StepPin, HIGH);
        digitalWrite(state.pump4StepPin, LOW);
        break;
    default:
        break;
    }
}

void setValves(){
    digitalWrite(state.valve1Pin, state.valve1);
    digitalWrite(state.valve2Pin, state.valve2);
    digitalWrite(state.valve3Pin, state.valve3);
    digitalWrite(state.valve4Pin, state.valve4);
    digitalWrite(state.valve5Pin, state.valve5);
    digitalWrite(state.valve6Pin, state.valve6);
    digitalWrite(state.valve7Pin, state.valve7);
    digitalWrite(state.valve8Pin, state.valve8);
    digitalWrite(state.valve9Pin, state.valve9);
    digitalWrite(state.valve10Pin, state.valve10);
    digitalWrite(state.valve11Pin, state.valve11);
    digitalWrite(state.valve12Pin, state.valve12);
    digitalWrite(state.valve13Pin, state.valve13);
    digitalWrite(state.valve14Pin, state.valve14);
    digitalWrite(state.valve15Pin, state.valve15);
    digitalWrite(state.valve16Pin, state.valve16);
}

//                                       REMEMBER TO CHANGE THE MODUID FOR EACH ARDUINO.        

//                                       Then label it, and put it on the spreadsheet.
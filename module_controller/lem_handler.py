import json
import os
import threading
import time
from typing import Dict, List, Any, Optional

import serial
import paho.mqtt.client as mqtt


SYS_SEQ_LEM_HEADER = [
    "nullLeader","modId","command","stateId","circFlow","pressureFlow",
    "valve1","valve2","valve3","valve4","valve5","valve6","valve7","valve8",
    "valve9","valve10","valve11","valve12","valve13","valve14","valve15","valve16",
    "transTimeFlag","transTimeSp","pressureSP","oxySP","presInterval","flowInterval",
    "oxyInterval","reportInterval","oxyTemp","oxyCircChannel","pumpSpeedRatio","circPumpCal",
    "pressurePumpCal","pressureKp","pressureKi","pressureKd","oxyKp","oxyKi","oxyKd",
    "flowInstalled","pressureInstalled","oxyInstalled","activeOxyChannel1","activeOxyChannel2",
    "activeOxyChannel3","activeOxyChannel4","pump1Cw","pump2Cw","pump3Cw","pump4Cw",
    "pump1DirPin","pump1StepPin","pump2DirPin","pump2StepPin","pump3DirPin","pump3StepPin",
    "pump4DirPin","pump4StepPin","valve1Pin","valve2Pin","valve3Pin","valve4Pin","valve5Pin",
    "valve6Pin","valve7Pin","valve8Pin","valve9Pin","valve10Pin","valve11Pin","valve12Pin",
    "valve13Pin","valve14Pin","valve15Pin","valve16Pin","oxyConfigParameter","pressure0Address",
    "pressureChannel","flow0Address","dispensePara","dispenseVolumeSP","pcBaudRate","oxyBaudRate",
    "pressureBaudRate","flagCheck","nullTrailer",
]

# Baseline values mirroring SYS_SEQ_LEM.csv second row (all valves off)
SYS_SEQ_LEM_BASELINE = [
    0,9101,1002,9101,0,0,
    0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,5000,37,1,0.9,
    0.003125,0.003125,2,5,1,1,3,0.1,0,0,0,0,0,0,
    0,1,1,1,1,37,38,35,36,33,34,31,32,30,29,28,27,26,25,24,23,2,3,4,5,6,7,8,9,47,54,0,8,
    0,0,115200,115200,115200,9101,0
]


class LEMHandler:
    def __init__(self, port: str, baud: int = 115200, mqtt_host: str = "127.0.0.1"):
        self.port = port
        self.baud = baud
        self._serial: Optional[serial.Serial] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._state: List[Any] = SYS_SEQ_LEM_BASELINE.copy()
        self.mod_uid: Optional[int] = None

        self.mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt.on_connect = self._on_mqtt_connect
        self.mqtt.on_message = self._on_mqtt_message
        self.mqtt.connect(mqtt_host)

        # Config file resides in sibling directory lem_software/lem_config.json
        self.config_path = os.path.join(os.path.dirname(__file__), "..", "lem_software", "lem_config.json")
        self.config_path = os.path.abspath(self.config_path)
        self.config: Dict[str, Any] = {}
        self._load_config()

    # ---------------- MQTT -----------------
    def _on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        try:
            self.mqtt.subscribe([("lem-commands", 0), ("lem-get-config", 0), ("lem-update-config", 0)])
        except Exception:
            pass

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        except Exception:
            return
        topic = msg.topic
        if topic == "lem-get-config":
            # Reload from disk to reflect any manual edits, then publish
            try:
                self._load_config()
            except Exception:
                pass
            self._publish_config()
            return
        if topic == "lem-update-config":
            self._handle_update_config(payload)
            return
        if topic == "lem-commands":
            self._handle_lem_command(payload)

    def _publish_config(self):
        try:
            self.mqtt.publish("lem-config", json.dumps(self.config))
        except Exception:
            pass

    def _handle_update_config(self, payload: Dict[str, Any]):
        try:
            updated = {**self.config, **payload}
            required = ["LEM_DISPENSE_TARGET_VOLUME", "LEM_DISPENSE_ACTUAL_VOLUME"]
            for key in required:
                if key not in updated:
                    self._publish_status({"type": "config_error", "error": f"Missing {key}"})
                    return
            self.config = updated
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            self._publish_status({"type": "config_updated", "ok": True})
            self._publish_config()
        except Exception as e:
            self._publish_status({"type": "config_error", "error": str(e)})

    def _handle_lem_command(self, payload: Dict[str, Any]):
        msg = payload.get("message") or payload
        command = msg.get("command")
        if command == "stop_lem":
            self._send_stop()
        elif command == "lem_dispense":
            valve_index = int(msg.get("valve_index"))
            volume_ml = float(msg.get("volume_ml"))
            self._send_dispense(valve_index, volume_ml)

    def _publish_status(self, obj: Dict[str, Any]):
        try:
            self.mqtt.publish("lem-status", json.dumps(obj))
        except Exception:
            pass

    def _publish_raw(self, line: str):
        try:
            self.mqtt.publish("lem-status-raw", line)
        except Exception:
            pass

    # --------------- Config ---------------
    def _load_config(self):
        if not os.path.exists(self.config_path):
            defaults = {
                "LEM_DISPENSE_TARGET_VOLUME": 10,
                "LEM_DISPENSE_ACTUAL_VOLUME": 22,
                "circPumpCal": 0.003125,
                "pressurePumpCal": 0.003125,
            }
            self.config = defaults
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(defaults, f, indent=2)
            except Exception:
                pass
        else:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception:
                self.config = {}

    # --------------- Serial ---------------
    def start(self):
        if self._running:
            return
        self._running = True
        try:
            self._serial = serial.Serial(self.port, self.baud, timeout=0.1)
        except Exception as e:
            self._publish_status({"type": "error", "error": f"Failed to open {self.port}: {e}"})
            self._running = False
            return
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()
        threading.Thread(target=self.mqtt.loop_forever, daemon=True).start()

    def stop(self):
        self._running = False
        try:
            if self._serial:
                self._serial.close()
        except Exception:
            pass

    def _reader_loop(self):
        while self._running and self._serial:
            try:
                raw = self._serial.readline()
            except Exception:
                time.sleep(0.05)
                continue
            if not raw:
                continue
            try:
                line = raw.decode(errors="ignore").strip()
            except Exception:
                continue
            if not line:
                continue
            self._publish_raw(line)
            parts = [p for p in line.strip().strip(',').split(',') if p != ""]
            if len(parts) >= 3 and parts[2] in ("1001", "1515"):
                try:
                    mod_uid = int(parts[1])
                    self.mod_uid = mod_uid
                except Exception:
                    pass
                if parts[2] == "1001":
                    obj = {"type": "state_request", "modUID": self.mod_uid, "transId": int(parts[3]) if len(parts) > 3 else None}
                    self._publish_status(obj)
                elif parts[2] == "1515":
                    rep = {"type": "report", "modUID": self.mod_uid, "stateId": int(parts[3]) if len(parts) > 3 else None}
                    self._publish_status(rep)

    # --------------- CSV building ---------------
    def _reset_valves(self, state: List[Any]):
        for idx, name in enumerate(SYS_SEQ_LEM_HEADER):
            if name.startswith("valve") and not name.endswith("Pin"):
                state[idx] = 0

    def _send_stop(self):
        state = self._state.copy()
        self._reset_valves(state)
        state[SYS_SEQ_LEM_HEADER.index("dispensePara")] = 0
        state[SYS_SEQ_LEM_HEADER.index("dispenseVolumeSP")] = 0
        self._send_state(state)
        self._publish_status({"type": "stop_sent"})

    def _send_dispense(self, valve_index: int, volume_ml: float):
        try:
            tgt = float(self.config["LEM_DISPENSE_TARGET_VOLUME"])
            act = float(self.config["LEM_DISPENSE_ACTUAL_VOLUME"])
            circ_cal = 0.003125
            pres_cal = 0.003125
        except Exception:
            self._publish_status({"type": "config_error", "error": "Missing or invalid correction/calibration values in lem_config.json"})
            return

        dose = volume_ml * (tgt / act)
        state = self._state.copy()
        self._reset_valves(state)
        valve_key = f"valve{int(valve_index)}"
        if valve_key not in SYS_SEQ_LEM_HEADER:
            self._publish_status({"type": "error", "error": f"Invalid valve_index {valve_index}"})
            return
        state[SYS_SEQ_LEM_HEADER.index(valve_key)] = 1
        pump_index = ((int(valve_index) - 1) // 4) + 1
        state[SYS_SEQ_LEM_HEADER.index("dispensePara")] = pump_index
        state[SYS_SEQ_LEM_HEADER.index("dispenseVolumeSP")] = dose
        state[SYS_SEQ_LEM_HEADER.index("circPumpCal")] = circ_cal
        state[SYS_SEQ_LEM_HEADER.index("pressurePumpCal")] = pres_cal
        self._send_state(state)
        self._publish_status({"type": "dispense_sent", "valve_index": valve_index, "pump_index": pump_index, "volume_ml": volume_ml, "dose_sp": dose})

    def _send_state(self, state: List[Any]):
        idx_mod = SYS_SEQ_LEM_HEADER.index("modId")
        idx_stateid = SYS_SEQ_LEM_HEADER.index("stateId")
        if self.mod_uid is not None:
            state[idx_mod] = self.mod_uid
            state[idx_stateid] = self.mod_uid
        state[SYS_SEQ_LEM_HEADER.index("command")] = 1002
        self._state = state.copy()
        parts: List[str] = []
        for v in state:
            if isinstance(v, bool):
                parts.append("1" if v else "0")
            elif isinstance(v, int):
                parts.append(str(v))
            elif isinstance(v, float):
                parts.append(str(v))
            elif v is None:
                parts.append("0")
            else:
                parts.append(str(v))
        line = ",".join(parts) + ",\n"
        # Publish debug copy before writing to serial
        try:
            self.mqtt.publish("lem-debug", line)
        except Exception:
            pass
        try:
            if self._serial:
                self._serial.write(line.encode("utf-8"))
        except Exception as e:
            self._publish_status({"type": "error", "error": f"Serial write failed: {e}"})



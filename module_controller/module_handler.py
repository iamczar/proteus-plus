import threading
import os
import time
import json
import csv
from typing import Optional, Callable, Any, Dict, List
from datetime import datetime
import serial
import paho.mqtt.client as mqtt
from common.logger import Logger


class ModuleHandler:
    def __init__(
        self,
        module_name: str,
        module_id: int,
        port: str,
        baudrate: int,
        logger: Logger,
        on_disconnect: Optional[Callable[[int, str, Optional[Exception]], None]] = None,
    ):
        self.module_name = module_name
        self.module_id = module_id
        self.port = port
        self.baudrate = baudrate
        self.logger = logger
        self.on_disconnect = on_disconnect

        self._serial: Optional[serial.Serial] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._write_lock = threading.Lock()
        # Own MQTT client for per-module commands and status
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.on_connect = self._on_mqtt_connect
        # Use per-topic callbacks; avoid a single catch-all handler
        self.mqtt_client.connect("127.0.0.1")
        self._mqtt_thread: Optional[threading.Thread] = None
        # Sequence sending session state
        self._sequence_rows: Optional[List[Dict[str, Any]]] = None
        # Experiment/logging context
        self._experiment_dir: Optional[str] = None
        self._run_id: Optional[str] = None
        self._sequence_filename: Optional[str] = None
        self._data_logging_enabled: bool = False
        self._alpha_logging_active: bool = False
        self._data_csv_path: Optional[str] = None
        self._data_csv_file = None
        self._data_csv_writer = None

    def start(self):
        if self._running:
            return
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=0.1)
        except Exception as e:
            self.logger.error(f"{self.module_name}: failed to open {self.port}: {e}")
            self._notify_disconnect(e)
            return

        self._running = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        # Start MQTT loop for command subscriptions
        self._mqtt_thread = threading.Thread(target=self.mqtt_client.loop_forever, daemon=True)
        self._mqtt_thread.start()
        self.logger.info(f"{self.module_name}: started on {self.port}")

    def stop(self):
        self._running = False
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
        except Exception:
            pass
        self._serial = None
        # Close any open data file
        try:
            if self._data_csv_file:
                try:
                    self._data_csv_file.flush()
                except Exception:
                    pass
                self._data_csv_file.close()
        except Exception:
            pass
        self._data_csv_file = None
        self._data_csv_writer = None
        try:
            self.mqtt_client.disconnect()
        except Exception:
            pass
        self.logger.info(f"{self.module_name}: stopped")

    def restart(self):
        self.stop()

    # MQTT handlers
    def _on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        try:
            rc_int = int(reason_code)
        except Exception:
            rc_int = int(getattr(reason_code, "value", 1)) if hasattr(reason_code, "value") else 1
        if rc_int == 0:
            try:
                # Subscribe to per-module command topics
                topics = [
                    (f"sequence-commands/{self.module_id}", 0),
                    (f"autosampler-command/{self.module_id}", 0),
                    (f"wrist-command/{self.module_id}", 0),
                    (f"pid-commands/{self.module_id}", 0),
                ]
                client.subscribe(topics)
                # Attach simple per-topic callbacks
                client.message_callback_add(f"sequence-commands/{self.module_id}", self._cb_sequence_commands)
                client.message_callback_add(f"autosampler-command/{self.module_id}", self._cb_autosampler_command)
                client.message_callback_add(f"wrist-command/{self.module_id}", self._cb_wrist_command)
                client.message_callback_add(f"pid-commands/{self.module_id}", self._cb_pid_commands)
                self.logger.info(f"{self.module_name}: subscribed to command topics")
            except Exception as e:
                self.logger.warn(f"{self.module_name}: subscribe failed: {e}")

    # Per-topic callbacks (simplified)
    def _cb_sequence_commands(self, client, userdata, msg):
        try:
            payload = self._decode_payload(msg.payload)
            # Expect envelope {message_source, timestamp, message: {...}}
            inner = self._extract_inner_message(payload)
            if inner is None:
                self.logger.warn(f"{self.module_name}: invalid sequence payload: {payload}")
                return

            cmd = str(inner.get("command", "")).strip()
            if cmd == "set_experiment_context":
                # {experiment_dir, run_id?, sequence_filename?}
                exp_dir = inner.get("experiment_dir")
                run_id = inner.get("run_id")
                seq_fn = inner.get("sequence_filename")
                if isinstance(exp_dir, str) and exp_dir:
                    try:
                        os.makedirs(exp_dir, exist_ok=True)
                        self._experiment_dir = exp_dir
                        self._run_id = str(run_id) if run_id else None
                        self._sequence_filename = str(seq_fn) if seq_fn else None
                        # Reset data file so it will reopen on next log write
                        self._close_data_file()
                        self._data_csv_path = None
                        self.logger.info(f"{self.module_name}: experiment context set -> {exp_dir}")
                    except Exception as e:
                        self.logger.warn(f"{self.module_name}: failed to set experiment context: {e}")
                return
            if cmd == "start_sequence":
                file_path = inner.get("file_path")
                if not file_path:
                    self.logger.warn(f"{self.module_name}: start_sequence missing file_path")
                    return
                rows = self._read_sequence_csv(str(file_path))
                if not rows:
                    self.logger.warn(f"{self.module_name}: CSV has no rows: {file_path}")
                    return
                self._sequence_rows = rows
                init_msg = {"command": "sequence_cmd", "number_of_states": len(rows)}
                self.send(self._wrap_alpha_envelope(init_msg))
                return

            # Map UI commands to Alpha commands
            ui_to_alpha = {
                "stop_sequence": "stop",
                "pause_sequence": "pause",
                "resume_sequence": "resume",
                "retrieve_data": "retrieve_data",
                "start_data_log": "start_data_log",
                "stop_data_log": "stop_data_log",
                "clear_session_logs": "clear_session_logs",
            }
            if cmd in ui_to_alpha:
                self.send(self._wrap_alpha_envelope({"command": ui_to_alpha[cmd]}))
                # Mirror UI logging command locally to start/stop file writes
                if cmd == "start_data_log":
                    self._data_logging_enabled = True
                elif cmd == "stop_data_log":
                    self._data_logging_enabled = False
                return

            # Backward-compatible legacy payloads (plain string or direct sequence_cmd)
            normalized = self._normalize_sequence_payload(inner)
            if normalized is not None:
                self.send(self._wrap_alpha_envelope(normalized))
        except Exception as e:
            self.logger.warn(f"{self.module_name}: sequence command error: {e}")

    def _cb_autosampler_command(self, client, userdata, msg):
        try:
            payload = self._decode_payload(msg.payload)
            # Accept either full envelope {message:{...}} or bare dict
            inner_msg = self._extract_inner_message(payload)
            cmd_src = inner_msg if inner_msg is not None else payload
            # Expect payload to contain sampler_id, cmd, hold_time, delay_seconds
            inner: Dict[str, Any] = {"command": "auto_sampler_cmd"}
            if isinstance(cmd_src, dict):
                # Normalize keys
                if "sampler_id" in cmd_src:
                    inner["sampler_id"] = cmd_src.get("sampler_id")
                if "cmd" in cmd_src:
                    inner["cmd"] = cmd_src.get("cmd")
                if "hold_time" in cmd_src:
                    inner["hold_time"] = cmd_src.get("hold_time")
                if "delay_seconds" in cmd_src:
                    inner["delay_seconds"] = cmd_src.get("delay_seconds")
            elif isinstance(cmd_src, str):
                # Allow simple named commands; map to cmd integers if needed by Alpha later
                inner["named_cmd"] = cmd_src
            self.send(self._wrap_alpha_envelope(inner))
        except Exception as e:
            self.logger.warn(f"{self.module_name}: autosampler command error: {e}")

    def _cb_wrist_command(self, client, userdata, msg):
        try:
            payload = self._decode_payload(msg.payload)
            wrist_value: Any = payload.get("wrist_cmd") if isinstance(payload, dict) else payload
            try:
                wrist_value = int(wrist_value)
            except Exception:
                pass
            inner = {"command": "wrist_cmd", "wrist_cmd": wrist_value}
            self.send(self._wrap_alpha_envelope(inner))
        except Exception as e:
            self.logger.warn(f"{self.module_name}: wrist command error: {e}")

    def _cb_pid_commands(self, client, userdata, msg):
        try:
            payload = self._decode_payload(msg.payload)
            inner = {"command": "pid_cmd", "payload": payload}
            self.send(self._wrap_alpha_envelope(inner))
        except Exception as e:
            self.logger.warn(f"{self.module_name}: pid command error: {e}")

    

    def send(self, message: dict):
        data = json.dumps(message) + "\n"
        try:
            with self._write_lock:
                if not self._serial or not self._serial.is_open:
                    raise Exception("serial not open")
                self._serial.write(data.encode())
        except Exception as e:
            self.logger.warn(f"{self.module_name}: write failed: {e}")
            self._notify_disconnect(e)

    # Topic-aware translation helpers
    def _utc_timestamp(self) -> str:
        # Match alphacommsmanager_test.py (naive ISO timestamp)
        return datetime.now().isoformat()

    def _wrap_alpha_envelope(self, inner: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message_source": "proteus",
            "timestamp": self._utc_timestamp(),
            "message": inner,
        }

    def _decode_payload(self, raw: Any) -> Any:
        text = raw.decode(errors="ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)
        try:
            return json.loads(text)
        except Exception:
            return text.strip()

    def _extract_inner_message(self, payload: Any) -> Optional[Dict[str, Any]]:
        if isinstance(payload, dict):
            if isinstance(payload.get("message"), dict):
                return dict(payload.get("message"))
            # If already inner object, accept
            return dict(payload)
        if isinstance(payload, str) and payload:
            return {"command": payload}
        return None

    def _normalize_sequence_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        # Accept direct string commands like "stop", "pause", "resume", etc.
        if isinstance(payload, str) and payload:
            return {"command": payload}
        if not isinstance(payload, dict):
            return None
        # If a command is provided, forward as-is inside message
        if "command" in payload:
            return dict(payload)
        # Map test formats from alphacommsmanager_test.py
        if "number_of_states" in payload:
            return {"command": "sequence_cmd", "number_of_states": payload["number_of_states"]}
        if "sequence_number" in payload and "state" in payload:
            return {
                "command": "sequence_cmd",
                "sequence_number": payload["sequence_number"],
                "state": payload["state"],
            }
        return None

    # CSV reader similar to tests/send_sequence_from_csv.py
    def _coerce_value(self, value: str, typ: Optional[str]) -> Any:
        if typ is None:
            v = value.strip()
            if v in ("1", "0"):
                return v == "1"
            try:
                if "." in v:
                    return float(v)
                return int(v)
            except Exception:
                return v
        try:
            t = typ.strip().lower()
            v = value.strip()
            if t in ("bool", "boolean"):
                return v in ("1", "true", "True")
            if t in ("int", "integer"):
                return int(float(v))
            if t in ("double", "float"):
                return float(v)
            return v
        except Exception:
            return value

    def _read_sequence_csv(self, path: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        try:
            with open(path, newline="") as f:
                reader = csv.reader(f)
                all_rows = list(reader)
            if not all_rows:
                return rows
            headers = [h.strip() for h in all_rows[0]]
            types: Optional[List[str]] = None
            start_idx = 1
            if len(all_rows) > 1 and any(t in ("int", "bool", "double", "float") for t in all_rows[1]):
                types = [t.strip() for t in all_rows[1]]
                start_idx = 2
            for r in all_rows[start_idx:]:
                if not any((cell or "").strip() for cell in r):
                    continue
                obj: Dict[str, Any] = {}
                for i, h in enumerate(headers):
                    val = r[i] if i < len(r) else ""
                    typ = types[i] if (types and i < len(types)) else None
                    obj[h] = self._coerce_value(val, typ)
                rows.append(obj)
        except Exception as e:
            self.logger.warn(f"{self.module_name}: failed to read CSV {path}: {e}")
        return rows

    def _read_loop(self):
        topic_status = f"module/{self.module_id}/status"
        while self._running:
            try:
                if not self._serial or not self._serial.is_open:
                    raise Exception("serial closed")
                raw = self._serial.readline()
            except Exception as e:
                if self._running:
                    self.logger.warn(f"{self.module_name}: read error: {e}")
                    self._notify_disconnect(e)
                break

            if not raw:
                continue
            try:
                line = raw.decode(errors="ignore").strip()
                if not line:
                    continue
                obj = json.loads(line)
            except Exception:
                continue

            if "module_id" not in obj:
                obj["module_id"] = self.module_id

            try:
                # Always publish raw line to module status
                self.mqtt_client.publish(topic_status, json.dumps(obj))
                # Route to specific topics
                routed_topic = self._select_outbound_topic(obj)
                if routed_topic:
                    self.mqtt_client.publish(routed_topic, json.dumps(obj))
                # Track Alpha data_logger logging state via system message
                try:
                    src_local = str(obj.get("message_source", "")).lower()
                    if src_local == "data_logger" and isinstance(obj.get("message"), dict):
                        msg = obj["message"]
                        if msg.get("event") == "logging_state":
                            self._alpha_logging_active = bool(msg.get("active"))
                            # Publish a concise status on data-logging/<module-id>
                            status_payload = {
                                "message_source": "module_handler",
                                "module_id": self.module_id,
                                "timestamp": self._utc_timestamp(),
                                "message": {
                                    "event": "logging_state",
                                    "active": self._alpha_logging_active,
                                },
                            }
                            self.mqtt_client.publish(f"data-logging/{self.module_id}", json.dumps(status_payload))
                except Exception:
                    pass
                # If this is data_logger sensor payload, mirror to CSV if enabled
                try:
                    src = str(obj.get("message_source", "")).lower()
                    if src == "data_logger" and self._data_logging_enabled and self._alpha_logging_active:
                        if obj.get("alpha_command") == "sensor_data" and isinstance(obj.get("data"), dict):
                            self._write_data_log_row(obj)
                except Exception:
                    pass
            except Exception as e:
                self.logger.warn(f"{self.module_name}: mqtt publish failed: {e}")

            # Respond to AlphaCommsManager sequence_request directly from serial
            try:
                command = obj.get("command")
                if not command and isinstance(obj.get("message"), dict):
                    command = obj["message"].get("command")
                if command == "sequence_request":
                    req = obj.get("sequence_request")
                    if req is None and isinstance(obj.get("message"), dict):
                        req = obj["message"].get("sequence_request")
                    if isinstance(req, (int, float, str)):
                        try:
                            idx = int(req)
                        except Exception:
                            idx = None
                        if idx is not None and self._sequence_rows and 0 <= idx < len(self._sequence_rows):
                            row = self._sequence_rows[idx]
                            state = {k: v for k, v in row.items() if k != "cmd"}
                            payload = {
                                "command": "sequence_cmd",
                                "sequence_number": idx,
                                "state": state,
                            }
                            self.send(self._wrap_alpha_envelope(payload))
            except Exception as e:
                self.logger.debug(f"{self.module_name}: failed to respond to sequence_request: {e}")

    def _select_outbound_topic(self, obj: Dict[str, Any]) -> Optional[str]:
        try:
            source = str(obj.get("message_source", "")).lower()
            inner = obj.get("message") if isinstance(obj.get("message"), dict) else {}

            # Explicit routing rules:
            # - data_logger:
            #   * sensor_data -> live-sensor-data
            #   * maintenance/status events (logging_state, maintenance_entered, maintenance_scan,
            #     delete_failed, logs_cleared, etc.) -> sys-logger
            if source == "data_logger":
                inner_msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
                alpha_cmd = obj.get("alpha_command")
                # Route sensor stream distinctly
                if alpha_cmd == "sensor_data" or (isinstance(inner_msg, dict) and "data" in obj):
                    # Filter out logging_state system messages from the sensor stream
                    if isinstance(inner_msg, dict) and inner_msg.get("event") == "logging_state":
                        return None
                    return f"live-sensor-data/{self.module_id}"
                # All other data_logger system events go to sys-logger
                return f"sys-logger/{self.module_id}"

            # - PID status routing from controllers
            if source == "pid_flow":
                return f"pid-flow-status/{self.module_id}"
            if source == "pid_pressure":
                return f"pid-pressure-status/{self.module_id}"

            # - data_logger_ack -> sys-logger (explicit maintenance/status acks)
            if source == "data_logger_ack":
                return f"sys-logger/{self.module_id}"

            # - SysLogger -> sys-logger
            if source == "syslogger":
                return f"sys-logger/{self.module_id}"

            # - Sequence controller state/acks -> sequence-controller-status
            if source == "sequence_controller":
                return f"sequence-controller-status/{self.module_id}"

            # - AlphaCommsManager state notifications -> alphacommsmanager-status
            if source == "alpha_comms_manager":
                # Mirror auto sampler acks into autosampler-status as well
                try:
                    if isinstance(inner, dict) and inner.get("command") == "auto_sampler_cmd_ack":
                        self.mqtt_client.publish(
                            f"autosampler-status/{self.module_id}", json.dumps(obj)
                        )
                except Exception:
                    pass
                return f"alphacommsmanager-status/{self.module_id}"

            # - file_storage_sensor -> file-info
            if source == "file_storage_sensor":
                return f"file-info/{self.module_id}"

            # - auto_sampler -> autosampler-status
            if source == "auto_sampler":
                return f"autosampler-status/{self.module_id}"

            # Also route to file-info if an explicit file_path is present
            if (isinstance(obj, dict) and ("file_path" in obj)) or (isinstance(inner, dict) and ("file_path" in inner)):
                return f"file-info/{self.module_id}"

            # Otherwise, do not fan-out to a specific routed topic
            return None
        except Exception:
            return None

    def _notify_disconnect(self, error: Optional[Exception] = None):
        if self.on_disconnect:
            try:
                self.on_disconnect(self.module_id, self.port, error)
            except Exception:
                pass
        self.stop()

    # ------------------- Data logging helpers -------------------
    def _ensure_data_file(self) -> None:
        if not self._experiment_dir:
            return
        if self._data_csv_writer is not None:
            return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"{self.module_id}_data_{ts}.csv" if not self._run_id else f"{self.module_id}_data_{self._run_id}.csv"
            path = os.path.join(self._experiment_dir, base_name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            f = open(path, "w", newline="")
            writer = csv.writer(f)
            # Header matching example 3006_data.csv
            header = [
                "TIME","NULLEADER","MODUID","COMMAND","STATEID","OXYMEASURED","PRESSUREMEASURED","FLOWMEASURED","TEMPMEASURED",
                "CIRCPUMPSPEED","PRESSUREPUMPSPEED","PRESSUREPID","PRESSURESETPOINT","PRESSUREKP","PRESSUREKI","PRESSUREKD",
                "OXYGENPID","OXYGENSETPOINT","OXYGENKP","OXYGENKI","OXYGENKD","OXYGENMEASURED1","OXYGENMEASURED2","OXYGENMEASURED3","OXYGENMEASURED4","NULLTRAILER"
            ]
            writer.writerow(header)
            self._data_csv_file = f
            self._data_csv_writer = writer
            self._data_csv_path = path
            self.logger.info(f"{self.module_name}: data log file opened -> {path}")
        except Exception as e:
            self.logger.warn(f"{self.module_name}: failed to open data file: {e}")

    def _close_data_file(self) -> None:
        try:
            if self._data_csv_file:
                try:
                    self._data_csv_file.flush()
                except Exception:
                    pass
                self._data_csv_file.close()
        except Exception:
            pass
        self._data_csv_file = None
        self._data_csv_writer = None

    def _write_data_log_row(self, obj: Dict[str, Any]) -> None:
        if not self._experiment_dir:
            return
        if self._data_csv_writer is None:
            self._ensure_data_file()
            if self._data_csv_writer is None:
                return
        try:
            ts = obj.get("timestamp") or datetime.now().isoformat()
            module_id = int(obj.get("module_id", self.module_id))
            alpha_cmd = obj.get("alpha_command")
            data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
            def num(key: str, default: float = 0.0) -> float:
                try:
                    v = data.get(key, default)
                    return float(v)
                except Exception:
                    return float(default)
            def intval(val, default: int = 0) -> int:
                try:
                    return int(float(val))
                except Exception:
                    return default
            row = [
                ts,
                0,
                module_id,
                intval(alpha_cmd, 1515),
                intval(data.get("state_id", 0)),
                num("oxy_measured", 0.0),
                num("pressure_measured", 0.0),
                num("flow_measured", 0.0),
                num("temp_measured", 0.0),
                num("circ_pump_speed", 0.0),
                num("pressure_pump_speed", 0.0),
                num("pressure_pid", 0.0),
                num("pressure_setpoint", 0.0),
                num("pressure_kp", 0.0),
                num("pressure_ki", 0.0),
                num("pressure_kd", 0.0),
                num("oxygen_pid", 0.0),
                num("oxygen_setpoint", 0.0),
                num("oxygen_kp", 0.0),
                num("oxygen_ki", 0.0),
                num("oxygen_kd", 0.0),
                num("oxygen_measured_1", 0.0),
                num("oxygen_measured_2", 0.0),
                num("oxygen_measured_3", 0.0),
                num("oxygen_measured_4", 0.0),
                0,
            ]
            self._data_csv_writer.writerow(row)
            try:
                self._data_csv_file.flush()
            except Exception:
                pass
        except Exception as e:
            self.logger.warn(f"{self.module_name}: failed to write data row: {e}")



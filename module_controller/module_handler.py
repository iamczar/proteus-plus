import threading
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
        try:
            self.mqtt_client.disconnect()
        except Exception:
            pass
        self.logger.info(f"{self.module_name}: stopped")

    def restart(self):
        self.stop()

    # MQTT handlers
    def _on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        if int(reason_code) == 0:
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
            }
            if cmd in ui_to_alpha:
                self.send(self._wrap_alpha_envelope({"command": ui_to_alpha[cmd]}))
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
            inner: Dict[str, Any] = {"command": "autosampler_cmd", "payload": payload}
            if isinstance(payload, dict) and "command" in payload:
                inner["autosampler_command"] = payload.get("command")
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
            # file-info if file_path present in either level
            if (isinstance(obj, dict) and ("file_path" in obj)) or (isinstance(inner, dict) and ("file_path" in inner)):
                return f"file-info/{self.module_id}"
            # wrist status
            if "wrist" in source:
                return f"wrist-status/{self.module_id}"
            # autosampler status
            if "auto" in source and "sampler" in source:
                return f"autosampler-status/{self.module_id}"
            # system logger style messages
            if source in ("alpha_comms_manager", "sequence_controller"):
                return f"sys-logger/{self.module_id}"
            # default live sensor data
            return f"live-sensor-data/{self.module_id}"
        except Exception:
            return None

    def _notify_disconnect(self, error: Optional[Exception] = None):
        if self.on_disconnect:
            try:
                self.on_disconnect(self.module_id, self.port, error)
            except Exception:
                pass
        self.stop()



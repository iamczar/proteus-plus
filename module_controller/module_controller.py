import threading
import time
import json
import serial
import serial.tools.list_ports
from typing import Dict, Optional
import paho.mqtt.client as mqtt
from common.logger import Logger
from common.mqtt_base_class import MqttBaseClass
from .module_handler import ModuleHandler
from .lem_handler import LEMHandler


class ModuleController(MqttBaseClass):
    def __init__(self, mqtt_client: mqtt.Client, logger: Logger, 
                 scan_interval: float = 5.0, id_request_timeout: float = 2.0):
        # MQTT topics for module controller
        # Only listen for controller commands; module status is forwarded by handlers
        sub_topics = [("controller/command", 0)]
        super().__init__(mqtt_client, sub_topics, logger)

        self.scan_interval = scan_interval
        self.id_request_timeout = id_request_timeout
        self.module_handlers: Dict[int, ModuleHandler] = {}
        self.scanning = False
        self.running = False

        self.scanning_ports: Dict[str, float] = {}

        self.baudrate = 115200
        self.timeout = 0.1
        self.detection_timeout = 3.0

        # Track single LEM handler separately from regular modules
        self.lem_handler: Optional[LEMHandler] = None
        self.lem_active: bool = False
        self.lem_port: Optional[str] = None

        self.logger.info("ModuleController initialized")

    def start(self):
        self.running = True
        self.scanning = True
        threading.Thread(target=self._scan_loop, daemon=True).start()
        threading.Thread(target=self._module_list_publisher_loop, daemon=True).start()
        threading.Thread(target=self.start_mqtt_loop, daemon=True).start()
        self.logger.info("ModuleController started")
        # Publish initial (possibly empty) module list immediately
        try:
            self._publish_module_list()
        except Exception:
            pass

    def stop(self):
        self.running = False
        self.scanning = False
        for module_id, handler in self.module_handlers.items():
            self.logger.info(f"Stopping module handler for module {module_id}")
            handler.stop()
        self.module_handlers.clear()
        # Stop LEM handler if active
        if self.lem_handler is not None:
            try:
                self.lem_handler.stop()
            except Exception:
                pass
            self.lem_handler = None
            self.lem_active = False
            try:
                payload = {"source": "module_controller", "lem_active": False, "timestamp": time.time()}
                self.mqtt_client.publish("module_controller/lem-status", json.dumps(payload))
            except Exception:
                pass
        self.logger.info("ModuleController stopped")
        # Publish final empty list to indicate no modules are managed
        try:
            self._publish_module_list()
        except Exception:
            pass

    def _module_list_publisher_loop(self):
        """Periodically publish the list of connected module IDs."""
        while self.running:
            try:
                payload = {
                    "command": "module_list",
                    "modules": list(self.module_handlers.keys()),
                    "timestamp": time.time(),
                }
                self.mqtt_client.publish("module_controller/list-of-modules", json.dumps(payload))
                # Also publish LEM heartbeat status
                lem_payload = {
                    "command": "lem_status",
                    "lem_active": bool(self.lem_active),
                    "port": self.lem_port,
                    "timestamp": time.time(),
                }
                self.mqtt_client.publish("module_controller/lem-status", json.dumps(lem_payload))
            except Exception as e:
                self.logger.debug(f"Failed to publish module list: {e}")
            time.sleep(2.0)

    def _scan_loop(self):
        while self.scanning and self.running:
            try:
                self._scan_serial_ports()
                time.sleep(self.scan_interval)
            except Exception as e:
                self.logger.error(f"Error in scan loop: {e}")
                time.sleep(1.0)

    def _scan_serial_ports(self):
        managed_ports = set([h.port for h in self.module_handlers.values()])
        try:
            comports = list(serial.tools.list_ports.comports())
        except Exception as e:
            self.logger.error(f"Failed to list serial ports: {e}")
            comports = []

        available_devices = set([getattr(p, "device", None) for p in comports if getattr(p, "device", None)])
        # Detect LEM disconnect
        if self.lem_active and self.lem_port and self.lem_port not in available_devices:
            self.logger.warn(f"LEM disconnected from {self.lem_port}")
            try:
                if self.lem_handler:
                    self.lem_handler.stop()
            except Exception:
                pass
            self.lem_handler = None
            self.lem_active = False
            old_port = self.lem_port
            self.lem_port = None
            try:
                payload = {"source": "module_controller", "lem_active": False, "port": old_port, "timestamp": time.time()}
                self.mqtt_client.publish("module_controller/lem-status", json.dumps(payload))
            except Exception:
                pass

        for port_info in comports:
            port = getattr(port_info, "device", None)
            description = getattr(port_info, "description", "") or ""
            vid = getattr(port_info, "vid", None)
            pid = getattr(port_info, "pid", None)

            is_usb_serial = ("USB" in description) or (vid is not None and pid is not None)
            if not port or not is_usb_serial:
                continue

            if port in managed_ports or port in self.scanning_ports:
                continue

            self.scanning_ports[port] = time.time()
            try:
                self._detect_module_on_port(port)
            finally:
                if port in self.scanning_ports:
                    del self.scanning_ports[port]

    def _detect_module_on_port(self, port: str):
        start_time = time.time()
        try:
            ser = serial.Serial(port, self.baudrate, timeout=self.timeout)
        except Exception as e:
            self.logger.debug(f"Could not open {port} for detection: {e}")
            return

        detected_module_id: Optional[int] = None
        detected_lem: bool = False
        try:
            while time.time() - start_time < self.detection_timeout:
                try:
                    raw = ser.readline()
                except Exception as read_err:
                    self.logger.debug(f"Read error on {port}: {read_err}")
                    break
                if not raw:
                    continue
                try:
                    line = raw.decode(errors="ignore").strip()
                except Exception:
                    continue
                if not line:
                    continue
                # Try LEM CSV detection first: token[2]==1001 and token[1]==9101
                parts = [p for p in line.strip().strip(',').split(',') if p != ""]
                if len(parts) >= 3 and parts[2] == "1001":
                    try:
                        moduid = int(parts[1])
                        if moduid == 9101:
                            detected_lem = True
                            detected_module_id = 9101
                            break
                    except Exception:
                        pass
                # Fallback to JSON-based detection (other modules)
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                module_id_value = obj.get("module_id")
                if module_id_value is None and isinstance(obj.get("message"), dict):
                    module_id_value = obj["message"].get("module_id")
                if module_id_value is not None:
                    try:
                        detected_module_id = int(module_id_value)
                    except Exception:
                        self.logger.debug(f"Non-integer module_id on {port}: {module_id_value}")
                        continue
                    break
        finally:
            try:
                ser.close()
            except Exception:
                pass

        if detected_module_id is None:
            self.logger.debug(f"No module_id detected on {port} within {self.detection_timeout}s")
            return

        if detected_module_id in self.module_handlers:
            self.logger.info(f"Module {detected_module_id} already has a handler; skipping {port}")
            return

        if detected_lem and detected_module_id == 9101:
            try:
                # If already active, ignore duplicate detection
                if self.lem_handler is None:
                    self.lem_handler = LEMHandler(port, self.baudrate)
                    self.lem_handler.start()
                    self.lem_active = True
                    self.lem_port = port
                    self.logger.info(f"Detected LEM (9101) on {port}")
                    try:
                        payload = {"source": "module_controller", "lem_active": True, "port": port, "timestamp": time.time()}
                        self.mqtt_client.publish("module_controller/lem-status", json.dumps(payload))
                    except Exception:
                        pass
            except Exception as e:
                self.logger.error(f"Failed to start LEMHandler on {port}: {e}")
        else:
            handler = self._create_module_handler(detected_module_id, port)
            if handler:
                self.logger.info(f"Detected module {detected_module_id} on {port}")

    def _create_module_handler(self, module_id: int, port: str) -> Optional[ModuleHandler]:
        try:
            handler = ModuleHandler(
                module_name=f"module_{module_id}",
                module_id=module_id,
                port=port,
                baudrate=self.baudrate,
                logger=self.logger,
                on_disconnect=self._on_handler_disconnected
            )
            handler.start()
            self.module_handlers[module_id] = handler
            self.logger.info(f"Created module handler for module {module_id} on {port}")
            # Publish updated module list immediately
            try:
                self._publish_module_list()
            except Exception:
                pass
            return handler
        except Exception as e:
            self.logger.error(f"Failed to create module handler for {module_id} on {port}: {e}")
            return None

    def is_a_valid_message(self, msg_json_obj) -> bool:
        # With serial sniffing, the controller only needs to accept controller commands
        return isinstance(msg_json_obj, dict) and ("command" in msg_json_obj)

    def handle_message(self, msg_json_obj):
        try:
            self._handle_controller_command(msg_json_obj)
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    def _handle_id_response(self, msg_json_obj):
        module_id = msg_json_obj.get("module_id")
        port = msg_json_obj.get("port")
        if not module_id or not port:
            self.logger.warn("Invalid ID response: missing module_id or port")
            return
        if module_id in self.module_handlers:
            self.logger.info(f"Module {module_id} already has a handler")
            return
        handler = self._create_module_handler(module_id, port)
        if handler:
            self.logger.info(f"Successfully created handler for module {module_id}")

    def _handle_status_message(self, msg_json_obj):
        module_id = msg_json_obj.get("module_id")
        status = msg_json_obj.get("status")
        self.logger.debug(f"Module {module_id} status: {status}")

    def _handle_controller_command(self, msg_json_obj):
        command = msg_json_obj.get("command")
        if command == "stop_all":
            self.logger.info("Received stop_all command")
            self.stop()
        elif command == "restart_all":
            self.logger.info("Received restart_all command")
            self._restart_all_handlers()
        elif command == "list_modules":
            self._publish_module_list()

    def _restart_all_handlers(self):
        for module_id, handler in self.module_handlers.items():
            try:
                handler.restart()
                self.logger.info(f"Restarted handler for module {module_id}")
            except Exception as e:
                self.logger.error(f"Failed to restart handler for module {module_id}: {e}")

    def _on_handler_disconnected(self, module_id: int, port: str, error: Optional[Exception] = None):
        if module_id in self.module_handlers:
            self.logger.warn(f"Handler disconnected for module {module_id} on {port}: {error}")
            try:
                self.module_handlers[module_id].stop()
            except Exception:
                pass
            del self.module_handlers[module_id]
            try:
                payload = {
                    "command": "module_disconnected",
                    "module_id": module_id,
                    "port": port,
                    "timestamp": time.time()
                }
                self.mqtt_client.publish("controller/status", json.dumps(payload))
            except Exception:
                pass
            # Publish updated module list after removal
            try:
                self._publish_module_list()
            except Exception:
                pass

    def _publish_module_list(self):
        module_list = {
            "command": "module_list",
            "modules": list(self.module_handlers.keys()),  # LEM excluded by design
            "timestamp": time.time(),
        }
        self.mqtt_client.publish("module_controller/list-of-modules", json.dumps(module_list))

    def run(self):
        self.start()
        try:
            while self.running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            self.stop()

    def get_module_handler(self, module_id: int) -> Optional[ModuleHandler]:
        return self.module_handlers.get(module_id)

    def get_active_modules(self) -> list:
        return list(self.module_handlers.keys())

    def send_to_module(self, module_id: int, message: dict):
        handler = self.get_module_handler(module_id)
        if handler:
            handler.send(message)
        else:
            self.logger.warn(f"No handler found for module {module_id}")



import threading
import time
import json
from typing import Optional, Callable
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
        self.mqtt_client.on_message = self._on_mqtt_message
        self.mqtt_client.connect("127.0.0.1")
        self._mqtt_thread: Optional[threading.Thread] = None

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
                    (f"wrist-cmd/{self.module_id}", 0),
                    (f"heartbeat/{self.module_id}", 0),
                ]
                client.subscribe(topics)
                self.logger.info(f"{self.module_name}: subscribed to command topics")
            except Exception as e:
                self.logger.warn(f"{self.module_name}: subscribe failed: {e}")

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode(errors="ignore")
            # Forward the raw payload to serial
            self.send(json.loads(payload))
        except Exception as e:
            self.logger.warn(f"{self.module_name}: command handling failed: {e}")
        time.sleep(0.1)
        self.start()

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
                self.mqtt_client.publish(topic_status, json.dumps(obj))
            except Exception as e:
                self.logger.warn(f"{self.module_name}: mqtt publish failed: {e}")

    def _notify_disconnect(self, error: Optional[Exception] = None):
        if self.on_disconnect:
            try:
                self.on_disconnect(self.module_id, self.port, error)
            except Exception:
                pass
        self.stop()



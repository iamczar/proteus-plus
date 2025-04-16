# module_handler.py

import threading
import queue
import serial
import json
import time
from common.logger import Logger
import paho.mqtt.client as mqtt

class ModuleHandler:
    def __init__(self, module_name: str, module_id: int, port: str, baudrate: int,
                 mqtt_client: mqtt.Client, logger: Logger):
        self.module_name = module_name
        self.module_id = module_id
        self.port = port
        self.baudrate = baudrate
        self.mqtt_client = mqtt_client
        self.logger = logger

        self.ser = None
        self.tx_queue = queue.Queue()
        self.running = False

    def start(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.running = True

            threading.Thread(target=self._rx_loop, daemon=True).start()
            threading.Thread(target=self._tx_loop, daemon=True).start()

            self.logger.info(f"[{self.module_name}] ModuleHandler started on {self.port}")
        except Exception as e:
            self.logger.error(f"[{self.module_name}] Failed to start: {e}")

    def stop(self):
        self.running = False
        if self.ser:
            try:
                self.ser.close()
                self.logger.info(f"[{self.module_name}] Serial port closed.")
            except Exception as e:
                self.logger.error(f"[{self.module_name}] Error on stop: {e}")
                
    def restart(self):
        self.logger.info(f"[{self.module_name}] Restarting ModuleHandler...")
        self.stop()
        time.sleep(1.0)  # Small delay before reopening serial port
        self.start()
    
    def send(self, message: dict):
        try:
            payload = json.dumps(message) + "\n"
            self.tx_queue.put(payload.encode())
        except Exception as e:
            self.logger.error(f"[{self.module_name}] Failed to queue TX: {e}")

    def _tx_loop(self):
        while self.running:
            try:
                data = self.tx_queue.get(timeout=0.1)
                self.ser.write(data)
                self.logger.debug(f"[{self.module_name}] TX: {data}")
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"[{self.module_name}] TX error: {e}")

    def _rx_loop(self):
        while self.running:
            try:
                if self.ser.in_waiting:
                    line = self.ser.readline().strip()
                    decoded = line.decode(errors="ignore")
                    self.logger.debug(f"[{self.module_name}] RX: {decoded}")

                    try:
                        msg_json = json.loads(decoded)
                        topic = f"module/{self.module_id}/rx"
                        self.mqtt_client.publish(topic, json.dumps(msg_json))
                    except json.JSONDecodeError:
                        self.logger.warning(f"[{self.module_name}] Invalid JSON: {decoded}")

            except Exception as e:
                self.logger.error(f"[{self.module_name}] RX error: {e}")

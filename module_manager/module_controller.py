import threading
import time
import json
import serial
import serial.tools.list_ports
from typing import Dict, Optional
import paho.mqtt.client as mqtt
from common.logger import Logger
from common.mqtt_base_class import MqttBaseClass
from module_handler import ModuleHandler


class ModuleController(MqttBaseClass):
    def __init__(self, mqtt_client: mqtt.Client, logger: Logger, 
                 scan_interval: float = 5.0, id_request_timeout: float = 2.0):
        """
        Module Controller that manages serial connections and module handlers.
        
        Args:
            mqtt_client: MQTT client for communication
            logger: Logger instance
            scan_interval: How often to scan for new serial ports (seconds)
            id_request_timeout: Timeout for ID request responses (seconds)
        """
        # MQTT topics for module controller
        sub_topics = [
            ("module/+/id_response", 0),  # Listen for ID responses from modules
            ("module/+/status", 0),       # Listen for module status updates
            ("controller/command", 0)      # Listen for controller commands
        ]
        
        super().__init__(mqtt_client, sub_topics, logger)
        
        self.scan_interval = scan_interval
        self.id_request_timeout = id_request_timeout
        self.module_handlers: Dict[int, ModuleHandler] = {}
        self.scanning = False
        self.running = False
        
        # Track ports being tested for ID requests
        self.pending_id_requests: Dict[str, float] = {}  # port -> timestamp
        
        # Serial port configuration
        self.baudrate = 115200
        self.timeout = 0.1
        
        self.logger.info("ModuleController initialized")

    def start(self):
        """Start the module controller."""
        self.running = True
        self.scanning = True
        
        # Start scanning thread
        threading.Thread(target=self._scan_loop, daemon=True).start()
        
        # Start MQTT loop
        threading.Thread(target=self.start_mqtt_loop, daemon=True).start()
        
        self.logger.info("ModuleController started")

    def stop(self):
        """Stop the module controller and all module handlers."""
        self.running = False
        self.scanning = False
        
        # Stop all module handlers
        for module_id, handler in self.module_handlers.items():
            self.logger.info(f"Stopping module handler for module {module_id}")
            handler.stop()
        
        self.module_handlers.clear()
        self.logger.info("ModuleController stopped")

    def _scan_loop(self):
        """Main scanning loop that periodically checks for new serial ports."""
        while self.scanning and self.running:
            try:
                self._scan_serial_ports()
                time.sleep(self.scan_interval)
            except Exception as e:
                self.logger.error(f"Error in scan loop: {e}")
                time.sleep(1.0)

    def _scan_serial_ports(self):
        """Scan available serial ports and test for module responses."""
        available_ports = [port.device for port in serial.tools.list_ports.comports()]
        
        for port in available_ports:
            if port not in self.module_handlers.values() and port not in self.pending_id_requests:
                self._test_port_for_module(port)

    def _test_port_for_module(self, port: str):
        """Test a serial port by sending an ID request."""
        try:
            # Open temporary serial connection
            ser = serial.Serial(port, self.baudrate, timeout=self.timeout)
            
            # Send ID request
            id_request = {"command": "get_id", "timestamp": time.time()}
            request_json = json.dumps(id_request) + "\n"
            ser.write(request_json.encode())
            
            # Mark as pending
            self.pending_id_requests[port] = time.time()
            
            # Close temporary connection
            ser.close()
            
            self.logger.debug(f"Sent ID request to {port}")
            
        except Exception as e:
            self.logger.debug(f"Could not test {port}: {e}")

    def _cleanup_pending_requests(self):
        """Remove expired ID request timeouts."""
        current_time = time.time()
        expired_ports = []
        
        for port, timestamp in self.pending_id_requests.items():
            if current_time - timestamp > self.id_request_timeout:
                expired_ports.append(port)
        
        for port in expired_ports:
            del self.pending_id_requests[port]
            self.logger.debug(f"ID request timeout for {port}")

    def _create_module_handler(self, module_id: int, port: str) -> Optional[ModuleHandler]:
        """Create a new module handler for the given module."""
        try:
            # Create module handler
            handler = ModuleHandler(
                module_name=f"module_{module_id}",
                module_id=module_id,
                port=port,
                baudrate=self.baudrate,
                mqtt_client=self.mqtt_client,
                logger=self.logger
            )
            
            # Start the handler
            handler.start()
            
            # Store in dictionary
            self.module_handlers[module_id] = handler
            
            self.logger.info(f"Created module handler for module {module_id} on {port}")
            return handler
            
        except Exception as e:
            self.logger.error(f"Failed to create module handler for {module_id} on {port}: {e}")
            return None

    def is_a_valid_message(self, msg_json_obj) -> bool:
        """Check if the received message is valid for the module controller."""
        if not isinstance(msg_json_obj, dict):
            return False
        
        # Check for ID response messages
        if "module_id" in msg_json_obj and "response_type" in msg_json_obj:
            return msg_json_obj.get("response_type") == "id_response"
        
        # Check for status messages
        if "module_id" in msg_json_obj and "status" in msg_json_obj:
            return True
        
        # Check for controller commands
        if "command" in msg_json_obj:
            return True
        
        return False

    def handle_message(self, msg_json_obj):
        """Handle incoming MQTT messages."""
        try:
            # Handle ID response messages
            if msg_json_obj.get("response_type") == "id_response":
                self._handle_id_response(msg_json_obj)
            
            # Handle status messages
            elif "status" in msg_json_obj:
                self._handle_status_message(msg_json_obj)
            
            # Handle controller commands
            elif "command" in msg_json_obj:
                self._handle_controller_command(msg_json_obj)
                
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    def _handle_id_response(self, msg_json_obj):
        """Handle ID response from a module."""
        module_id = msg_json_obj.get("module_id")
        port = msg_json_obj.get("port")
        
        if not module_id or not port:
            self.logger.warn("Invalid ID response: missing module_id or port")
            return
        
        # Remove from pending requests
        if port in self.pending_id_requests:
            del self.pending_id_requests[port]
        
        # Check if we already have a handler for this module
        if module_id in self.module_handlers:
            self.logger.info(f"Module {module_id} already has a handler")
            return
        
        # Create new module handler
        handler = self._create_module_handler(module_id, port)
        if handler:
            self.logger.info(f"Successfully created handler for module {module_id}")

    def _handle_status_message(self, msg_json_obj):
        """Handle status messages from modules."""
        module_id = msg_json_obj.get("module_id")
        status = msg_json_obj.get("status")
        
        self.logger.debug(f"Module {module_id} status: {status}")

    def _handle_controller_command(self, msg_json_obj):
        """Handle controller commands."""
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
        """Restart all module handlers."""
        for module_id, handler in self.module_handlers.items():
            try:
                handler.restart()
                self.logger.info(f"Restarted handler for module {module_id}")
            except Exception as e:
                self.logger.error(f"Failed to restart handler for module {module_id}: {e}")

    def _publish_module_list(self):
        """Publish list of active modules."""
        module_list = {
            "command": "module_list",
            "modules": list(self.module_handlers.keys()),
            "timestamp": time.time()
        }
        
        self.mqtt_client.publish("controller/status", json.dumps(module_list))

    def run(self):
        """Main run method - starts the controller."""
        self.start()
        
        try:
            # Keep the main thread alive
            while self.running:
                self._cleanup_pending_requests()
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            self.stop()

    def get_module_handler(self, module_id: int) -> Optional[ModuleHandler]:
        """Get a module handler by module ID."""
        return self.module_handlers.get(module_id)

    def get_active_modules(self) -> list:
        """Get list of active module IDs."""
        return list(self.module_handlers.keys())

    def send_to_module(self, module_id: int, message: dict):
        """Send a message to a specific module."""
        handler = self.get_module_handler(module_id)
        if handler:
            handler.send(message)
        else:
            self.logger.warn(f"No handler found for module {module_id}")


if __name__ == "__main__":
    # Example usage
    import paho.mqtt.client as mqtt
    
    # Create logger
    logger = Logger("ModuleController", "module_controller.log", "info", True, True)
    
    # Create MQTT client
    mqtt_client = mqtt.Client()
    # Note: These flags are used by the MqttBaseClass but may not be standard attributes
    # The base class will handle connection management
    
    # Create and run controller
    controller = ModuleController(mqtt_client, logger)
    controller.run()
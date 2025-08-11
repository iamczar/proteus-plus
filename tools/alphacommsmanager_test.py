"""
AlphaCommsManager Test Script

This script tests the AlphaCommsManager on the MicroPython device.
It sends various commands and verifies the responses to ensure proper
communication between Proteus and the AlphaCommsManager.

Commands tested:
- stop: Stop all operations
- start_data_log: Start data logging
- stop_data_log: Stop data logging  
- retrieve_data: Retrieve logged data
- pause: Pause operations
- resume: Resume operations
- sequence_cmd: Sequence file handling (init + line data)

The sequence test sends 3 sequence lines with varying data to test
the JSONL file storage functionality.
"""

import serial
import time
import json
import sys
from datetime import datetime

def print_with_timestamp(message):
    """Print message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")

class AlphaCommsManagerTester:
    def __init__(self, port='COM4', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        
    def connect(self):
        """Connect to the serial port"""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print_with_timestamp(f"Connected to {self.port} at {self.baudrate} baudrate")
            return True
        except Exception as e:
            print_with_timestamp(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from serial port"""
        if self.ser:
            self.ser.close()
            print_with_timestamp("Disconnected")
    
    def send_command(self, command_json):
        """Send a JSON command to AlphaCommsManager"""
        try:
            command_str = json.dumps(command_json) + "\n"
            self.ser.write(command_str.encode())
            print_with_timestamp(f"SENT: {command_str.strip()}")
            return True
        except Exception as e:
            print_with_timestamp(f"Error sending command: {e}")
            return False
    
    def read_response(self, timeout=15.0, expected_command=None):
        """Read response from AlphaCommsManager, looking for specific command acknowledgment"""
        try:
            start_time = time.time()
            buffer = ""
            
            while time.time() - start_time < timeout:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='replace')
                    buffer += data
                    
                    # Look for complete JSON messages
                    if '\n' in buffer:
                        lines = buffer.split('\n')
                        for line in lines[:-1]:  # Process all complete lines
                            line = line.strip()
                            if line:
                                try:
                                    response = json.loads(line)
                                    print_with_timestamp(f"RECEIVED: {line}")
                                    
                                    # Ensure response is a dictionary
                                    if not isinstance(response, dict):
                                        print_with_timestamp(f"Warning: Received non-dictionary response: {type(response)}")
                                        continue
                                    
                                    # If we're looking for a specific command acknowledgment
                                    if expected_command:
                                        # Check if command is at top level (legacy) or in message field (new format)
                                        command = response.get("command")
                                        if not command and "message" in response:
                                            message = response.get("message", {})
                                            if isinstance(message, dict):
                                                command = message.get("command")
                                            else:
                                                continue  # Skip if message is not a dict
                                        
                                        if command == expected_command:
                                            return response
                                        # Keep looking for the expected command
                                        else:
                                            # Debug: log what command we received vs what we're looking for
                                            if expected_command == "sequence_request":
                                                print_with_timestamp(f"DEBUG: Looking for '{expected_command}', received '{command}'")
                                    else:
                                        # Return the first valid JSON response
                                        return response
                                        
                                except json.JSONDecodeError:
                                    # Log the incomplete JSON but don't try to process it
                                    print_with_timestamp(f"Non-JSON response: {line}")
                                    continue  # Skip this line and continue looking
                        
                        # Keep incomplete line in buffer
                        buffer = lines[-1]
                
                time.sleep(0.05)  # Increased delay to prevent busy waiting
            
            print_with_timestamp(f"No expected response received within timeout (looking for: {expected_command})")
            return None
            
        except Exception as e:
            print_with_timestamp(f"Error reading response: {e}")
            return None
    
    def test_stop_command(self):
        """Test stop command"""
        print_with_timestamp("=== Testing STOP Command ===")
        command = {
            "message_source": "proteus",
            "timestamp": datetime.now().isoformat(),
            "message": {
                "command": "stop"
            }
        }
        
        if self.send_command(command):
            response = self.read_response(expected_command="stop")
            if response:
                # Check if command is at top level (legacy) or in message field (new format)
                response_command = response.get("command")
                if not response_command and "message" in response:
                    response_command = response.get("message", {}).get("command")
                
                if response_command == "stop":
                    print_with_timestamp("✅ STOP command test PASSED")
                    return True
                else:
                    print_with_timestamp("❌ STOP command test FAILED")
                    return False
            else:
                print_with_timestamp("❌ STOP command test FAILED")
                return False
    
    def test_start_data_log_command(self):
        """Test start data log command"""
        print_with_timestamp("=== Testing START_DATA_LOG Command ===")
        command = {
            "message_source": "proteus",
            "timestamp": datetime.now().isoformat(),
            "message": {
                "command": "start_data_log"
            }
        }
        
        if self.send_command(command):
            response = self.read_response(expected_command="start_data_log")
            if response:
                # Check if command is at top level (legacy) or in message field (new format)
                response_command = response.get("command")
                if not response_command and "message" in response:
                    response_command = response.get("message", {}).get("command")
                
                if response_command == "start_data_log":
                    print_with_timestamp("✅ START_DATA_LOG command test PASSED")
                    return True
                else:
                    print_with_timestamp("❌ START_DATA_LOG command test FAILED")
                    return False
            else:
                print_with_timestamp("❌ START_DATA_LOG command test FAILED")
                return False
    
    def test_stop_data_log_command(self):
        """Test stop data log command"""
        print_with_timestamp("=== Testing STOP_DATA_LOG Command ===")
        command = {
            "message_source": "proteus",
            "timestamp": datetime.now().isoformat(),
            "message": {
                "command": "stop_data_log"
            }
        }
        
        if self.send_command(command):
            response = self.read_response(expected_command="stop_data_log")
            if response:
                # Check if command is at top level (legacy) or in message field (new format)
                response_command = response.get("command")
                if not response_command and "message" in response:
                    response_command = response.get("message", {}).get("command")
                
                if response_command == "stop_data_log":
                    print_with_timestamp("✅ STOP_DATA_LOG command test PASSED")
                    return True
                else:
                    print_with_timestamp("❌ STOP_DATA_LOG command test FAILED")
                    return False
            else:
                print_with_timestamp("❌ STOP_DATA_LOG command test FAILED")
                return False
    
    def test_retrieve_data_command(self):
        """Test retrieve data command"""
        print_with_timestamp("=== Testing RETRIEVE_DATA Command ===")
        command = {
            "message_source": "proteus",
            "timestamp": datetime.now().isoformat(),
            "message": {
                "command": "retrieve_data"
            }
        }
        
        if self.send_command(command):
            response = self.read_response(expected_command="retrieve_data")
            if response:
                # Check if command is at top level (legacy) or in message field (new format)
                response_command = response.get("command")
                if not response_command and "message" in response:
                    response_command = response.get("message", {}).get("command")
                
                if response_command == "retrieve_data":
                    print_with_timestamp("✅ RETRIEVE_DATA command test PASSED")
                    return True
                else:
                    print_with_timestamp("❌ RETRIEVE_DATA command test FAILED")
                    return False
            else:
                print_with_timestamp("❌ RETRIEVE_DATA command test FAILED")
                return False
    
    def test_pause_command(self):
        """Test pause command"""
        print_with_timestamp("=== Testing PAUSE Command ===")
        command = {
            "message_source": "proteus",
            "timestamp": datetime.now().isoformat(),
            "message": {
                "command": "pause"
            }
        }
        
        if self.send_command(command):
            response = self.read_response(expected_command="pause")
            if response:
                # Check if command is at top level (legacy) or in message field (new format)
                response_command = response.get("command")
                if not response_command and "message" in response:
                    response_command = response.get("message", {}).get("command")
                
                if response_command == "pause":
                    print_with_timestamp("✅ PAUSE command test PASSED")
                    return True
                else:
                    print_with_timestamp("❌ PAUSE command test FAILED")
                    return False
            else:
                print_with_timestamp("❌ PAUSE command test FAILED")
                return False
    
    def test_resume_command(self):
        """Test resume command"""
        print_with_timestamp("=== Testing RESUME Command ===")
        command = {
            "message_source": "proteus",
            "timestamp": datetime.now().isoformat(),
            "message": {
                "command": "resume"
            }
        }
        
        if self.send_command(command):
            response = self.read_response(expected_command="resume")
            if response:
                # Check if command is at top level (legacy) or in message field (new format)
                response_command = response.get("command")
                if not response_command and "message" in response:
                    response_command = response.get("message", {}).get("command")
                
                if response_command == "resume":
                    print_with_timestamp("✅ RESUME command test PASSED")
                    return True
                else:
                    print_with_timestamp("❌ RESUME command test FAILED")
                    return False
            else:
                print_with_timestamp("❌ RESUME command test FAILED")
                return False
    
    def test_sequence_commands(self):
        """Test sequence commands"""
        print_with_timestamp("=== Testing SEQUENCE Commands ===")
        
        # Test sequence initialization
        init_command = {
            "message_source": "proteus",
            "timestamp": datetime.now().isoformat(),
            "message": {
                "command": "sequence_cmd",
                "number_of_states": 3
            }
        }
        
        if not self.send_command(init_command):
            print_with_timestamp("❌ Sequence init test FAILED")
            return False
        
        response = self.read_response(expected_command="sequence_ack")
        if response:
            # Check if command is at top level (legacy) or in message field (new format)
            response_command = response.get("command")
            if not response_command and "message" in response:
                response_command = response.get("message", {}).get("command")
            
            if response_command == "sequence_ack":
                print_with_timestamp("✅ Sequence init test PASSED")
            else:
                print_with_timestamp("❌ Sequence init acknowledgment test FAILED")
                return False
        else:
            print_with_timestamp("❌ Sequence init acknowledgment test FAILED")
            return False
        
        # Test sequence line data - wait for requests from AlphaCommsManager
        for i in range(3):
            # Wait for sequence request from AlphaCommsManager
            print_with_timestamp(f"Waiting for sequence request for line {i}...")
            request_response = self.read_response(expected_command="sequence_request", timeout=20.0)  # Increased timeout
            if not request_response:
                print_with_timestamp(f"❌ No sequence request received for line {i}")
                return False
            
            # Check if sequence_request is at top level or in message field
            requested_line = request_response.get("sequence_request")
            if not requested_line and "message" in request_response:
                requested_line = request_response.get("message", {}).get("sequence_request")
            
            if requested_line != i:
                print_with_timestamp(f"❌ Expected request for line {i}, got {requested_line}")
                return False
            
            print_with_timestamp(f"✅ Received sequence request for line {i}")
            
            # Add a small delay to ensure the device is ready
            time.sleep(0.1)
            
            # Send the sequence line data as JSON object with realistic values
            # Each sequence line has different values to test variety
            line_command = {
                "message_source": "proteus",
                "timestamp": datetime.now().isoformat(),
                "message": {
                    "command": "sequence_cmd",
                    "sequence_number": i,
                    "state": {
                        "cmd": i,  # Different command for each sequence
                        "circFlow": 100 + (i * 50),  # Varying flow rates
                        "pressureFlow": 200 + (i * 25),
                        "valve1": i % 2 == 0,  # Alternating valve states
                        "valve2": i % 2 == 1,
                        "valve3": False,
                        "valve4": False,
                        "valve5": False,
                        "valve6": False,
                        "valve7": False,
                        "valve8": False,
                        "valve9": False,
                        "valve10": False,
                        "airpump1": i % 2 == 0,
                        "airpump2": i % 2 == 1,
                        "pressureSP": 1.0 + (i * 0.5),
                        "oxySP": 1.0 + (i * 0.3),
                        "pressureKp": 1.0 + (i * 0.1),
                        "pressureKi": 1.0 + (i * 0.05),
                        "pressureKd": 1.0 + (i * 0.02),
                        "oxyKp": 1.0 + (i * 0.1),
                        "oxyKi": 1.0 + (i * 0.05),
                        "oxyKd": 1.0 + (i * 0.02),
                        "pump2Dir": True,
                        "pump1Dir": True,
                        "tube_bore": 1 + i,
                        "pump_2_speed_ratio": 1.0 + (i * 0.1),
                        "ascmds1": 1 + i,
                        "ascmds2": 1 + i,
                        "ascmds3": 1 + i,
                        "wristCmd": i,
                        "transTimeSec": 2 + i
                    }
                }
            }
            
            if not self.send_command(line_command):
                print_with_timestamp(f"❌ Sequence line {i} test FAILED")
                return False
            
            response = self.read_response(expected_command="sequence_ack")
            if response:
                # Check if command is at top level (legacy) or in message field (new format)
                response_command = response.get("command")
                if not response_command and "message" in response:
                    response_command = response.get("message", {}).get("command")
                
                if response_command == "sequence_ack":
                    print_with_timestamp(f"✅ Sequence line {i} test PASSED")
                else:
                    print_with_timestamp(f"❌ Sequence line {i} acknowledgment test FAILED")
                    return False
            else:
                print_with_timestamp(f"❌ Sequence line {i} acknowledgment test FAILED")
                return False
        
        # Check for completion
        response = self.read_response(expected_command="sequence_complete", timeout=15.0)
        if response:
            # Check if command is at top level (legacy) or in message field (new format)
            response_command = response.get("command")
            if not response_command and "message" in response:
                response_command = response.get("message", {}).get("command")
            
            if response_command == "sequence_complete":
                print_with_timestamp("✅ Sequence completion test PASSED")
                return True
            else:
                print_with_timestamp("❌ Sequence completion test FAILED")
                return False
        else:
            print_with_timestamp("❌ Sequence completion test FAILED")
            return False
    
    def run_all_tests(self):
        """Run all tests and report results"""
        print_with_timestamp("Starting AlphaCommsManager tests...")
        print_with_timestamp("=" * 50)
        
        tests = [
            self.test_stop_command,
            self.test_start_data_log_command,
            self.test_stop_data_log_command,
            self.test_retrieve_data_command,
            self.test_pause_command,
            self.test_resume_command,
            self.test_sequence_commands
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                if test():
                    passed += 1
                # Add delay between tests
                time.sleep(0.5)
            except Exception as e:
                print_with_timestamp(f"Error in test: {e}")
        
        print_with_timestamp("=" * 50)
        print_with_timestamp(f"Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print_with_timestamp("✅ All tests passed")
            return True
        else:
            print_with_timestamp("❌ Some tests failed")
            return False

def main():
    # Allow command line arguments for port and baudrate
    import sys
    
    port = 'COM4'
    baudrate = 115200
    
    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        baudrate = int(sys.argv[2])
    
    tester = AlphaCommsManagerTester(port=port, baudrate=baudrate)
    
    if not tester.connect():
        return False
    
    try:
        return tester.run_all_tests()
    finally:
        tester.disconnect()

if __name__ == "__main__":
    main() 
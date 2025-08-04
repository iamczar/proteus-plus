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
    def __init__(self, port='COM6', baudrate=115200):
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
    
    def read_response(self, timeout=10.0, expected_command=None):
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
                                    
                                    # If we're looking for a specific command acknowledgment
                                    if expected_command:
                                        if response.get("alpha_command") == expected_command:
                                            return response
                                        # Keep looking for the expected command
                                    else:
                                        # Return the first valid JSON response
                                        return response
                                        
                                except json.JSONDecodeError:
                                    print_with_timestamp(f"Non-JSON response: {line}")
                        
                        # Keep incomplete line in buffer
                        buffer = lines[-1]
                
                time.sleep(0.01)
            
            print_with_timestamp(f"No expected response received within timeout (looking for: {expected_command})")
            return None
            
        except Exception as e:
            print_with_timestamp(f"Error reading response: {e}")
            return None
    
    def test_stop_command(self):
        """Test stop command"""
        print_with_timestamp("=== Testing STOP Command ===")
        command = {
            "alpha_command": "stop",
            "message_source": "proteus"
        }
        
        if self.send_command(command):
            response = self.read_response(expected_command="stop")
            if response and response.get("alpha_command") == "stop":
                print_with_timestamp("✅ STOP command test PASSED")
                return True
            else:
                print_with_timestamp("❌ STOP command test FAILED")
                return False
    
    def test_start_data_log_command(self):
        """Test start data log command"""
        print_with_timestamp("=== Testing START_DATA_LOG Command ===")
        command = {
            "alpha_command": "start_data_log",
            "message_source": "proteus"
        }
        
        if self.send_command(command):
            response = self.read_response(expected_command="start_data_log")
            if response and response.get("alpha_command") == "start_data_log":
                print_with_timestamp("✅ START_DATA_LOG command test PASSED")
                return True
            else:
                print_with_timestamp("❌ START_DATA_LOG command test FAILED")
                return False
    
    def test_stop_data_log_command(self):
        """Test stop data log command"""
        print_with_timestamp("=== Testing STOP_DATA_LOG Command ===")
        command = {
            "alpha_command": "stop_data_log",
            "message_source": "proteus"
        }
        
        if self.send_command(command):
            response = self.read_response(expected_command="stop_data_log")
            if response and response.get("alpha_command") == "stop_data_log":
                print_with_timestamp("✅ STOP_DATA_LOG command test PASSED")
                return True
            else:
                print_with_timestamp("❌ STOP_DATA_LOG command test FAILED")
                return False
    
    def test_retrieve_data_command(self):
        """Test retrieve data command"""
        print_with_timestamp("=== Testing RETRIEVE_DATA Command ===")
        command = {
            "alpha_command": "retrieve_data",
            "message_source": "proteus"
        }
        
        if self.send_command(command):
            response = self.read_response(expected_command="retrieve_data")
            if response and response.get("alpha_command") == "retrieve_data":
                print_with_timestamp("✅ RETRIEVE_DATA command test PASSED")
                return True
            else:
                print_with_timestamp("❌ RETRIEVE_DATA command test FAILED")
                return False
    
    def test_pause_command(self):
        """Test pause command"""
        print_with_timestamp("=== Testing PAUSE Command ===")
        command = {
            "alpha_command": "pause",
            "message_source": "proteus"
        }
        
        if self.send_command(command):
            response = self.read_response(expected_command="pause")
            if response and response.get("alpha_command") == "pause":
                print_with_timestamp("✅ PAUSE command test PASSED")
                return True
            else:
                print_with_timestamp("❌ PAUSE command test FAILED")
                return False
    
    def test_resume_command(self):
        """Test resume command"""
        print_with_timestamp("=== Testing RESUME Command ===")
        command = {
            "alpha_command": "resume",
            "message_source": "proteus"
        }
        
        if self.send_command(command):
            response = self.read_response(expected_command="resume")
            if response and response.get("alpha_command") == "resume":
                print_with_timestamp("✅ RESUME command test PASSED")
                return True
            else:
                print_with_timestamp("❌ RESUME command test FAILED")
                return False
    
    def test_sequence_commands(self):
        """Test sequence commands"""
        print_with_timestamp("=== Testing SEQUENCE Commands ===")
        
        # Test sequence initialization
        init_command = {
            "alpha_command": "sequence_cmd",
            "message_source": "proteus",
            "number_of_states": 3
        }
        
        if not self.send_command(init_command):
            print_with_timestamp("❌ Sequence init test FAILED")
            return False
        
        response = self.read_response(expected_command="sequence_ack")
        if not response or response.get("alpha_command") != "sequence_ack":
            print_with_timestamp("❌ Sequence init acknowledgment test FAILED")
            return False
        
        print_with_timestamp("✅ Sequence init test PASSED")
        
        # Test sequence line data - wait for requests from AlphaCommsManager
        for i in range(3):
            # Wait for sequence request from AlphaCommsManager
            print_with_timestamp(f"Waiting for sequence request for line {i}...")
            request_response = self.read_response(expected_command="sequence_request")
            if not request_response:
                print_with_timestamp(f"❌ No sequence request received for line {i}")
                return False
            
            requested_line = request_response.get("sequence_request")
            if requested_line != i:
                print_with_timestamp(f"❌ Expected request for line {i}, got {requested_line}")
                return False
            
            print_with_timestamp(f"✅ Received sequence request for line {i}")
            
            # Send the sequence line data
            line_command = {
                "alpha_command": "sequence_cmd",
                "message_source": "proteus",
                "sequence_number": i,
                "state": [0,10,10,1,1,1,1,1,1,1,1,1,1,1,1,0,20,2,5,1,0.2,0.05,0.01,1,1,1,1.0,1,1,1,0,10]
                          
            }
            
            if not self.send_command(line_command):
                print_with_timestamp(f"❌ Sequence line {i} test FAILED")
                return False
            
            response = self.read_response(expected_command="sequence_ack")
            if not response or response.get("alpha_command") != "sequence_ack":
                print_with_timestamp(f"❌ Sequence line {i} acknowledgment test FAILED")
                return False
            
            print_with_timestamp(f"✅ Sequence line {i} test PASSED")
        
        # Check for completion
        response = self.read_response(expected_command="sequence_complete")
        if response and response.get("alpha_command") == "sequence_complete":
            print_with_timestamp("✅ Sequence completion test PASSED")
            return True
        else:
            print_with_timestamp("❌ Sequence completion test FAILED")
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print_with_timestamp("Starting AlphaCommsManager tests...")
        print_with_timestamp("=" * 50)
        
        if not self.connect():
            return False
        
        try:
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
                if test():
                    passed += 1
                time.sleep(0.5)  # Small delay between tests
            
            print_with_timestamp("=" * 50)
            print_with_timestamp(f"Test Results: {passed}/{total} tests passed")
            
            if passed == total:
                print_with_timestamp("🎉 ALL TESTS PASSED!")
            else:
                print_with_timestamp("❌ Some tests failed")
            
            return passed == total
            
        finally:
            self.disconnect()

def main():
    # Allow command line arguments for port and baudrate
    port = 'COM4'
    baudrate = 115200
    
    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        baudrate = int(sys.argv[2])
    
    tester = AlphaCommsManagerTester(port, baudrate)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 
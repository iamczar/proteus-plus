import serial
import time
import sys
from datetime import datetime

def print_with_timestamp(message):
    """Print message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")

def main():
    # Serial port configuration
    port = 'COM6'  # Change this to your actual port (COM6, /dev/ttyACM0, etc.)
    baudrate = 115200
    timeout = 1
    
    print(f"Starting serial listener on {port} at {baudrate} baudrate...")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    try:
        # Open serial port
        with serial.Serial(port, baudrate, timeout=timeout) as ser:
            print_with_timestamp(f"Connected to {port}")
            print_with_timestamp("Waiting for data...")
            print("-" * 50)
            
            buffer = ""
            
            while True:
                # Check if data is available
                if ser.in_waiting > 0:
                    try:
                        # Read available data
                        incoming_data = ser.read(ser.in_waiting).decode('utf-8', errors='replace')
                        buffer += incoming_data
                        
                        # Process complete lines
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            line = line.strip()
                            if line:  # Only print non-empty lines
                                print_with_timestamp(f"RECEIVED: {line}")
                                
                    except UnicodeDecodeError as e:
                        print_with_timestamp(f"DECODE ERROR: {e}")
                    except Exception as e:
                        print_with_timestamp(f"READ ERROR: {e}")
                
                # Small delay to prevent CPU hogging
                time.sleep(0.01)
                
    except serial.SerialException as e:
        print(f"Serial port error: {e}")
        print("Make sure the device is connected and the port is correct.")
        print("Common ports:")
        print("  Windows: COM1, COM2, COM3, etc.")
        print("  Linux: /dev/ttyACM0, /dev/ttyUSB0, etc.")
        print("  Mac: /dev/tty.usbserial-*, /dev/tty.usbmodem*")
    except KeyboardInterrupt:
        print("\nStopped by user (Ctrl+C)")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    # Allow command line arguments for port and baudrate
    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        baudrate = int(sys.argv[2])
    
    main() 
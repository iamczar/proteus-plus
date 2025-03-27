import serial
import time
import socket
import json

# UDP Configuration
UDP_IP = "127.0.0.1"  # Adjust IP as needed
UDP_PORT = 8181       # PlotJuggler's UDP listening port

# Serial Configuration
SERIAL_PORT = "COM6"  # Change as needed
BAUDRATE = 115200

# Define SensorDataIndex mapping
SENSOR_KEYS = [
    "STATEID", "OXYMEASURED", "PRESSUREMEASURED", "FLOWMEASURED", "TEMPMEASURED",
    "CIRCPUMPSPEED", "PRESSUREPUMPSPEED", "PRESSUREPID", "PRESSURESETPOINT",
    "PRESSUREKP", "PRESSUREKI", "PRESSUREKD", "OXYGENPID", "OXYGENSETPOINT",
    "OXYGENKP", "OXYGENKI", "OXYGENKD", "OXYGENMEASURED1", "OXYGENMEASURED2",
    "OXYGENMEASURED3", "OXYGENMEASURED4"
]

# Create UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def is_valid_sensor_data(line):
    """Checks if the line is a valid sensor data line."""
    parts = line.strip().split(",")

    # Must have expected number of parts
    if len(parts) != len(SENSOR_KEYS) + 4:
        return False

    # Check if all parts are numeric (excluding empty strings)
    for part in parts:
        if part.replace(".", "").replace("-", "").isdigit() is False:
            return False  # If any part is not a number, it's not valid

    return True

def parse_message(line):
    """Parses a valid sensor data line into a key-value dictionary."""
    parts = line.strip().split(",")
    module_id = int(parts[1])    # Extract module ID
    command = int(parts[2])      # Extract command
    sensor_values = parts[3:-1]  # Extract sensor data (excluding first 3 and last value)

    parsed_data = {"MODULE_ID": module_id, "COMMAND": command}
    
    for key, value in zip(SENSOR_KEYS, sensor_values):
        try:
            parsed_data[key] = float(value) if "." in value else int(value)
        except ValueError:
            parsed_data[key] = None  # Handle invalid conversions

    return parsed_data

def send_udp(data):
    """Sends data over UDP in JSON format."""
    json_data = json.dumps(data)
    sock.sendto(json_data.encode(), (UDP_IP, UDP_PORT))

def main():
    try:
        with serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1) as ser:
            print(f"Connected to {SERIAL_PORT} at {BAUDRATE} baudrate.")

            while True:
                if ser.in_waiting > 0:
                    incoming_data = ser.readline().decode('utf-8', errors='ignore').strip()

                    if is_valid_sensor_data(incoming_data):  # Filter valid sensor lines
                        parsed_data = parse_message(incoming_data)
                        print(f"Sending: {parsed_data}")  # Debugging output
                        send_udp(parsed_data)

                time.sleep(0.1)

    except serial.SerialException as e:
        print(f"Serial port error: {e}")
    except KeyboardInterrupt:
        print("Exiting on user interrupt.")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()

import serial
import time

def main():
    port = 'COM6'  # Replace with your COM port, e.g., /dev/ttyUSB0 on Linux
    baudrate = 115200  # Adjust to match your device's baudrate

    try:
        # Open the serial port
        with serial.Serial(port, baudrate, timeout=1) as ser:
            print(f"Connected to {port} at {baudrate} baudrate.")
            while True:
                if ser.in_waiting > 0:  # Check if data is available
                    incoming_data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    print(f"Received: {incoming_data.strip()}")  # Print the incoming data
                time.sleep(0.1)  # Small delay to avoid busy waiting

    except serial.SerialException as e:
        print(f"Serial port error: {e}")
    except KeyboardInterrupt:
        print("Exiting on user interrupt.")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
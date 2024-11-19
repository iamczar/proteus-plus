import serial
import time


def all_off_commands():
        circFlowSpeed = 0
        pressureFlowSpeed = 0
        valve1 = 0
        valve2 = 0
        valve3 = 0
        valve4 = 0
        valve5 = 0
        valve6 = 0
        valve7 = 0
        valve8 = 0
        valve9 = 0
        valve10 = 0
        airpump1 = 0
        airpump2 = 0
        pressureSP = 0
        oxySP = 0
        pressureKp = 1.0
        pressureKi = 1.0
        pressureKd = 1.0
        oxyKp = 1.0
        oxyKi = 1.0
        oxyKd = 1.0
        pump2dir = 1
        pump1dir = 1
        tube_bore = 1
        pump_2_speed_ratio = 1.0        
        ascmd1 = 1
        ascmd2 = 1
        ascmd3 = 1
        wristCmd = 0
        
        # Create a comma-separated string of the values
        command_string = ",".join(map(str, [
            circFlowSpeed, pressureFlowSpeed, valve1, valve2, valve3, valve4, valve5,
            valve6, valve7, valve8, valve9, valve10, airpump1, airpump2, pressureSP,
            oxySP, pressureKp, pressureKi, pressureKd, oxyKp, oxyKi, oxyKd, pump2dir,
            pump1dir, tube_bore, pump_2_speed_ratio, ascmd1, ascmd2, ascmd3, wristCmd
        ]))

        return command_string + "\n"

def all_on_commands():
        circFlowSpeed = 5
        pressureFlowSpeed = 5
        valve1 = 1
        valve2 = 1
        valve3 = 1
        valve4 = 1
        valve5 = 1
        valve6 = 1
        valve7 = 1
        valve8 = 1
        valve9 = 1
        valve10 = 1
        airpump1 = 1
        airpump2 = 1
        pressureSP = 0
        oxySP = 0
        pressureKp = 1.0
        pressureKi = 1.0
        pressureKd = 1.0
        oxyKp = 1.0
        oxyKi = 1.0
        oxyKd = 1.0
        pump2dir = 1
        pump1dir = 1
        tube_bore = 1
        pump_2_speed_ratio = 1.0        
        ascmd1 = 1
        ascmd2 = 1
        ascmd3 = 1
        wristCmd = 0
        
        # Create a comma-separated string of the values
        command_string = ",".join(map(str, [
            circFlowSpeed, pressureFlowSpeed, valve1, valve2, valve3, valve4, valve5,
            valve6, valve7, valve8, valve9, valve10, airpump1, airpump2, pressureSP,
            oxySP, pressureKp, pressureKi, pressureKd, oxyKp, oxyKi, oxyKd, pump2dir,
            pump1dir, tube_bore, pump_2_speed_ratio, ascmd1, ascmd2, ascmd3, wristCmd
        ]))

        return command_string + "\n"

def main():
    # Define the serial port and settings (adjust COM port and baudrate as needed)
    port = 'COM5'  # Change this to the appropriate COM port
    baudrate = 115200  # Adjust to match your device's baudrate
    expected_message = "0,3004,1001,50,0\n"  # The message to trigger sending the command
    command = all_off_commands()
    #command = all_on_commands()
    # Open the serial port
    with serial.Serial(port, baudrate, timeout=1) as ser:
        print(f"Connected to {port} at {baudrate} baudrate.")
        buffer = ""
        
        while True:
            # Listen for incoming data from the target
            if ser.in_waiting > 0:
                incoming_data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')  # handle encoding errors
                buffer += incoming_data

                # Look for complete message in buffer
                if '\n' in buffer:
                    lines = buffer.split('\n')
                    for line in lines[:-1]:  # Process all complete lines
                        incoming_message = line.strip()
                        print(f"Received from target: {incoming_message}")
                        
                        # Check if the incoming message matches the expected message
                        if incoming_message == expected_message.strip():
                            # Send the command after receiving the expected message
                            ser.write(command.encode())
                            print(f"Host Sends: {command.strip()}")
                    
                    # Keep the last incomplete line in buffer (if any)
                    buffer = lines[-1]
                    
            # Small delay to avoid hogging CPU
            time.sleep(0.1)

if __name__ == "__main__":
    main()

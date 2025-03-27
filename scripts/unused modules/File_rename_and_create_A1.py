import os
from datetime import datetime
import csv
import sys

moduleID = sys.argv[1]  # Retrieve the moduleID from command-line arguments
expID = sys.argv[2]  # Retrieve the expID from command-line arguments

now = datetime.now() # current date and time
date_time2 = now.strftime("%Y-%m-%d-%H%M")
print("date and time:",date_time2)
cwd = os.getcwd()
print(cwd)

## Rename data.csv file
# expID = "NA" 

# filename_data=  os.path.join(cwd, "ALFI/2501_data.csv")
# filename_log = os.path.join(cwd, "ALFI/2501_log.csv")
filename_data=  os.path.join(cwd, f"{moduleID}/{moduleID}_data.csv")
filename_log = os.path.join(cwd, f"{moduleID}/{moduleID}_log.csv")

renameDataFile = f'{moduleID}/Data_files/{moduleID}_data_{date_time2}_{expID}.csv'
renameLogFile = f'{moduleID}/Log_files/{moduleID}_log_{date_time2}_{expID}.csv'
print("Renaming to:", renameDataFile)
print("Renaming to:", renameLogFile)

os.rename(filename_data, renameDataFile)
os.rename(filename_log, renameLogFile)
# os.rename(filename_data,renameDataFile,src_dir_fd=None, dst_dir_fd=None)
# os.rename(filename_log,renameLogFile,src_dir_fd=None, dst_dir_fd=None)

# Create empty 2501_data.csv and 2501_log.csv files
with open(filename_data, 'w') as creating_new_csv_file:
        pass
print("Empty Data File Created Successfully")
with open(filename_log, 'w') as creating_new_csv_file:
        pass
print("Empty Log File Created Successfully")

def add_custom_row(filename):
    # now = datetime.now() # current date and time
    date_time = now.strftime("%Y-%m-%d %H:%M:%S.%f") # format date and time

    # Define the new row
    new_row = [date_time, 0, moduleID, 1515, 4000, 0.00, 96.00, 0.00, 0.00, 0.00, 0.00, 0, 200.00, 2.00, 5.00, 1.00, 0, 20.00, 0.20, 0.05, 0.01, 0.00, 0.00, 0.00, 0.00, 0]

    with open(filename, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(new_row)

# Usage:
# add_custom_row('your_file.csv')
add_custom_row(filename_data)

import csv
import re
import sys

def check_csv_for_malformed_rows(file_path):
	wrong_columns_rows = []
	malformed_rows = []  # This list will hold rows that don't match the row pattern
	expected_columns = 27
	# Define the regex pattern for the entire row structure
	row_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+,(0|-\d+|\d+),\d+,\d+,\d+,-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,(0|\d+),-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,(0|\d+),-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,-?\d+\.\d+,(0|\d+),$')

	with open(file_path, mode='r', newline='', encoding='utf-8-sig') as csvfile:
		reader = csv.reader(csvfile)
		# Your existing code continues here...
		for row_number, row in enumerate(reader, start=1):
			joined_row = ','.join(row)
			if len(row) != expected_columns:
				wrong_columns_rows.append((row_number, row))
			elif not row_pattern.match(joined_row):
				malformed_rows.append((row_number, joined_row))
			# The character-specific check can be removed or adjusted as needed

	return wrong_columns_rows, malformed_rows

if __name__ == "__main__":
	if len(sys.argv) != 2:
		print("Usage: python script.py <path_to_csv_file>")
	else:
		file_path = sys.argv[1]
		wrong_columns_rows, malformed_rows = check_csv_for_malformed_rows(file_path)
		if wrong_columns_rows or malformed_rows:
			if wrong_columns_rows:
				print("Rows with wrong number of columns:")
				for row_number, row in wrong_columns_rows:
					print(f"Row {row_number}: {row}")
			if malformed_rows:
				print("Rows not matching the expected format:")
				for row_number, row in malformed_rows:
					print(f"Row {row_number}: {row}")
import sys
import argparse
import re

if __name__ == "__main__":
	filename = sys.argv[1]
	f = open(filename, "r")
	lines = f.readlines()
	for line in lines:
		if ',' in line:
			split_line = line.split(",")
			date = split_line[0]
			event_date = re.findall(r"[1-3]?[0-9]\s[A-Z][a-z][a-z]\s[1-2][0-9][0-9][0-9]", date)[0]
			print(event_date)
			event = split_line[1]
			place = split_line[2]
			child_parents = split_line[3]
			if len(split_line) > 4:
				print(split_line)
				witnesses = split_line[4]
				if " - " in witnesses:
					witnesses.strip("path.")
					witness_list = witnesses.split(" - ")
					print(witness_list)



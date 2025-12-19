import os
import re
import argparse

parser = argparse.ArgumentParser()

parser.add_argument('--flag', default="")
parser.add_argument('--query', default="", type=str)
parser.add_argument('--range', default=275, type=int)
parser.add_argument('--year', default=1750, type=int)
parser.add_argument('--parishes', default="", type=str)

def process_and_flag(f, query_string, flag_dict):
    filename = f.name
    query_words = query_string.split()
    for line in f:
        if "," in line:
            year_range = flag_dict["range"]
            year = flag_dict["year"]
            parishes = flag_dict["parishes"]
            query_split = line.split(",")
            record_year_match = re.search('[1|2][0-9][0-9][0-9]', query_split[0])
            if record_year_match:
            	record_year = record_year_match.group(0)
            	record_year_range = range(year - year_range, year + year_range)
            	if all(word in line for word in query_words) and int(record_year) in record_year_range:
                    print(filename + ": " + line)


def process_wb_and_flag(f, query_string, flag_dict):
    filename = f.name
    query_words = set(query_string.split())
    for line in f:
        data_words = set(line.split())
        intersect = data_words.intersection(query_words)
        if len(intersect) == len(query_words):
            print(filename + ": " + line)


def process_file(f, query_string, flag_dict):
    filename = f.name
    for line in f:
        year_range = flag_dict["range"]
        year = flag_dict["year"]
        parishes = flag_dict["parishes"]
        query_split = line.split(",")
        record_year_match = re.search('[1|2][0-9][0-9][0-9]', query_split[0])
        if record_year_match:
            record_year = int(record_year_match.group(0))
            record_year_range = range(year - year_range, year + year_range)
            if query_string in line and record_year in record_year_range:
                print(filename + ": " + line)


def open_and_search_files(query_string, flag, flag_dict):
    for filename in os.listdir(os.path.curdir):
        if filename.endswith(".in"):
            f = open(filename)
            if flag == 'and':
                process_and_flag(f, query_string, flag_dict)
            elif flag == 'wb_and':
                process_wb_and_flag(f, query_string, flag_dict)
            else:
                process_file(f, query_string, flag_dict)

if __name__ == "__main__":
    args = parser.parse_args()
    query_string = args.query
    flag = args.flag
    flag_dict = {}
    flag_dict["range"] = args.range
    flag_dict["year"] = args.year
    flag_dict["parishes"] = args.parishes
    open_and_search_files(query_string, flag, flag_dict)



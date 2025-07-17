import sys, re

forward_list = [30, 31, 30, 31, 31, 30, 31, 30, 31]
month_days_dict = {0: 31, 1: 31, 2:28, 3:31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
month_days_leap_dict = {0: 31, 1: 31, 2:29, 3:31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
month_convert = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

def is_leap_year(year):
	if year % 400 == 0:
		return True
	if (year % 4 == 0) and (year % 100 != 0):
		return True
	return False

def convert_forward(number, line):
	day = line[1]
	month = line[0]
	year = line[2]
	if number < 0:
		number = 0
	new_day = day+number

	while new_day > month_days_dict[month]:
		new_day = new_day-month_days_dict[month]
		month = month+1
	return [month, new_day, year]

def convert_backward(number, line):
	day = line[1]
	month = line[0]
	year = line[2]
	new_day = day-number
	if is_leap_year(year):
		while new_day <= 0:
			new_day = new_day+month_days_leap_dict[month-1]
			month = month-1
	else:
		while new_day <= 0:
			new_day = new_day+month_days_dict[month-1]
			month = month-1
	return [month, new_day, year]

def find_advent(number, line):
	approx = convert_forward(210, line)
	while approx[0] < 11 or (approx[0] == 11 and approx[1] < 27):
		approx = convert_forward(7, approx)
	if number > 0:
		return convert_forward((number-1)*7, approx)
	return approx

def find_epiph_sunday(number, line):
	approx = convert_backward(63, line)
	while (approx[0] > 1 or approx[1] > 13):
		approx = convert_backward(7, approx)
	if number > 0:
		return convert_forward((number-1)*7, approx)
	return approx



def convert_church_day(text, number, line):

	church_day_dict = {
		"p novum annum" : 0,
		"soendag efter nytaar" : 0,
		"p epiph" : find_epiph_sunday(number, line),
		"septuagesima" : convert_backward(9*7, line),
		"septuag" : convert_backward(9*7, line),
		"sexagesima" : convert_backward(8*7, line),
		"sexag" : convert_backward(8*7, line),
		"quinquagesima" : convert_backward(7*7, line),
		"quinquag" : convert_backward(7*7, line),
		"esto mihi" : convert_backward(7*7, line),
		"esto" : convert_backward(7*7, line),
		"fastelavn" : convert_backward(7*7, line),
		"askeonsdag" : convert_backward(6*7 + 4, line),
		"soendag i faste" : convert_backward((6*7) - (number-1)*7, line),
		"onsdag i faste" : convert_backward((6*7 + 4) - (number-1)*7, line),
		"quadragesima" : convert_backward(6*7, line),
		"quadrag" : convert_backward(6*7, line),
		"invocavit" : convert_backward(6*7, line),
		"invoc" : convert_backward(6*7, line),
		"reminiscere" : convert_backward(5*7, line),
		"remin" : convert_backward(5*7, line),
		"oculi" : convert_backward(4*7, line),
		"laetare" : convert_backward(3*7, line),
		"midfaste" : convert_backward(3*7, line),
		"judica" : convert_backward(2*7, line),
		"palmarum" : convert_backward(7, line),
		"viridium" : convert_backward(3, line),
		"skaertorsdag" : convert_backward(3, line),
		"langfredag" : convert_backward(2, line),
		"p pasch" : convert_forward(number*7, line),
		"efter paaske" : convert_forward(number*7, line),
		"paaskedag" : convert_forward(number-1, line),
		"pascha" : convert_forward(number-1, line),
		"quasimodogeniti" : convert_forward(7, line),
		"quasimodo" : convert_forward(7, line),
		"misericordia" : convert_forward(2*7, line),
		"jubilate" : convert_forward(3*7, line),
		"metonoia" : convert_forward(3*7+5, line),
		"store bededag" : convert_forward(3*7+5, line),
		"cantate" : convert_forward(4*7, line),
		"rogate" : convert_forward(5*7, line),
		"ascensionis" : convert_forward(5*7 + 4, line),
		"christi himmelfartsdag" : convert_forward(5*7 + 4, line),
		"exaudi" : convert_forward(6*7, line),
		"pentecost" : convert_forward(7*7 + number, line),
		"pinsedag" : convert_forward(7*7 + number, line),
		"trin" : convert_forward(8*7, line),
		"trinit" : convert_forward(8*7, line),
		"p trin" : convert_forward(8*7 + number*7, line),
		"p trinit" : convert_forward(8*7 + number*7, line),
		"adv" : find_advent(number % 5, line),
		"advent" : find_advent(number % 5, line),
		"p nativit" : find_advent(5, line)

	}
	return church_day_dict[text.strip()]

if __name__ == "__main__":
	f = open("easter500.txt", "r")
	file_lines = f.readlines()
	year_dict = {}
	for line in file_lines:
		split_line = line.split()
		split_line = [int(x) for x in split_line]
		year = split_line[2]
		year_dict[year] = split_line
	convert_test = convert_forward(63, [4, 9, 1699])
	year = 2000
	while(True):
		try:
			year = input("Enter year: ")
		except:
			print("Not a valid year")
		line = year_dict[year]
		church_day = raw_input("Enter a church day: ")
		church_day = church_day.replace(".", "").lower()
		church_day = church_day.replace("dom", "")
		church_day = church_day.replace("die", "")
		numbers = re.findall(r'\d+', church_day)
		number = 0
		if numbers:
			number = int(numbers[0])
			church_day = re.sub(str(number), "", church_day)
		converted = convert_church_day(church_day, number, line)
		result_month = converted[0]
		result_day = converted[1]
		result_year = converted[2]
		print(str(result_day) + " " + month_convert[result_month] + " " + str(result_year))
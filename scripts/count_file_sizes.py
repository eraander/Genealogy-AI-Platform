import os
from stat import *

file_endings = [".dk.in", ".ge.in", ".no.in", ".se.in", ".fi.in", ".ee.in", ".lv.in", ".lt.in", ".de.in", ".nl.in", ".be.in", ".lux.in", ".fr.in"
				".es.in", ".pt.in", ".ch.in", ".it.in", ".hu.in", ".cz.in", ".sk.in", ".slo.in", ".hr.in", ".srb.in", ".bg.in", ".ro.in", ".at.in",
				".by.in", ".ru.in", ".ua.in", ".ire.in", ".uk.in", ".usa.in", ".us.in"]


mappings = {".dk.in" : "Denmark", ".ge.in" : "Georgia", ".no.in" : "Norway", ".se.in" : "Sweden", ".fi.in" : "Finland", ".ee.in" : "Estonia", 
			".lv.in" : "Latvia", ".lt.in" : "Lithuania", ".de.in" : "Germany", ".nl.in" : "Netherlands", ".be.in" : "Belgium", ".lux.in" : "Luxembourg",
			".fr.in" : "France", ".es.in" : "Spain", ".pt.in" : "Portugal", ".ch.in" : "Switzerland", ".it.in" : "Italy", ".hu.in" : "Hungary", 
			".cz.in" : "Czechia", ".sk.in" : "Slovakia", ".slo.in" : "Slovenia", ".hr.in" : "Croatia", ".srb.in" : "Serbia", ".bg.in" : "Bulgaria", 
			".ro.in" : "Romania", ".at.in" : "Austria", ".by.in" : "Belarus", ".ru.in" : "Russia", ".ua.in" : "Ukraine", ".ire.in" : "Ireland", 
			".uk.in" : "UK", ".usa.in" : "USA", ".us.in" : "USA", ".in" : "Poland"}

if __name__ == "__main__":

	file_number = {}
	for key in mappings.keys():
		file_number[key] = 0

	file_bytes = {}
	for key in mappings.keys():
		file_bytes[key] = 0

	for file in os.listdir(os.path.curdir):
		has_ending = False
		for ending in file_endings:
			if ending in file:
				has_ending = True
				file_number[ending] += 1
				byte_size = os.path.getsize(file)
				file_bytes[ending] += byte_size
		if file.endswith(".in") and has_ending == False:
			print(file)
			file_number[".in"] += 1
			byte_size = os.path.getsize(file)
			file_bytes[".in"] += byte_size

	for key in mappings.keys():
		print(mappings[key] + " Records:\t" + str(file_number[key]) + " files\t" + str(file_bytes[key]) + " bytes")
	print("Total Records:\t" + str(sum(file_number.values())) + " files\t" + str(sum(file_bytes.values())) + " bytes")


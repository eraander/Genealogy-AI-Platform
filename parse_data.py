import re, json
from typing import Dict, List, Optional, Tuple

def parse_church_record(line: str) -> dict:
    raw_line = line.strip()
    raw_line = raw_line.replace("\xa0", " ")
    match = re.match(r"^(\d+)\.\s*(.*)$", raw_line)
    if match:
        entry_idx = int(match.group(1))
        content = match.group(2).strip()
    else:
        entry_idx = None
        content = raw_line
    parts = [p.strip() for p in content.split(",")]
    date, tag = parts[0], parts[1]

    # Marriages: Date, Tag, Groom ~ Bride, [Groomsmen], [Notes]
    if tag in ("tr", "m", "lys", "lys1", "proc"):
        groomsmen, notes = None, None
        if len(parts) > 3:
            if "test." in parts[3] or "forl." in parts[3]:
                groomsmen = parts[3]
            else:
                notes = ", ".join(parts[3:])
        if len(parts) > 4:
            notes = ", ".join(parts[4:])
        return {
            "record_type": "marriage",
            "entry_idx": entry_idx,
            "date": date,
            "tag": tag,
            "location": None,
            "spouses": parts[2],
            "groomsmen": groomsmen,
            "notes": notes,
        }

    # Deaths / Burials: Date, Tag, Location, Name/Designation, [Age], [Extra Info]
    if tag in ("d", "br", "dm", "dk", "d/br"):
        return {
            "record_type": "death",
            "entry_idx": entry_idx,
            "date": date,
            "tag": tag,
            "location": parts[2],
            "subject": parts[3],
            "age": parts[4] if len(parts) > 4 else None,
            "extra_info": ", ".join(parts[5:]) if len(parts) > 5 else None,
        }

    # Births / Baptisms: Date, Tag, Location, Child & Parents, [Witnesses], [Notes]
    if tag in ("b", "bt", "fm", "fk", "hjd"):
        witnesses, notes = None, None
        if len(parts) > 4:
            if "test." in parts[4] or "fadd." in parts[4]:
                witnesses = parts[4]
            else:
                notes = ", ".join(parts[4:])
        if len(parts) > 5:
            notes = ", ".join(parts[5:])
        return {
            "record_type": "birth",
            "entry_idx": entry_idx,
            "date": date,
            "tag": tag,
            "location": parts[2],
            "child_and_parents": parts[3] if len(parts) > 3 else None,
            "witnesses": witnesses,
            "notes": notes,
        }

    # Churching / Introductions (Tag 'intr'): Date, Tag, Location, Mother
    if tag == "intr":
        return {
            "record_type": "introduction",
            "entry_idx": entry_idx,
            "date": date,
            "tag": tag,
            "location": parts[2],
            "subject": parts[3] if len(parts) > 3 else None,
        }

    # Confirmations (Tag 'kf'): Handled by our earlier minimal kf parser
    if tag == "kf":
        return {
            "record_type": "confirmation",
            "entry_idx": entry_idx,
            "date": date,
            "tag": tag,
            "location": parts[2],
            "candidate": parts[3],
            "age": parts[4] if len(parts) == 6 else None,
            "relation_or_origin": parts[5] if len(parts) == 6 else None,
        }

    return {"raw": line}

def parse_record_header(line: str) -> Tuple[Optional[int], str, str, str, str]:
    """
    Strips the leading record number (if present) and splits by commas into:
    entry_idx, raw_date, event_token, location, and body.
    """
    raw_line = line.strip()
    raw_line = raw_line.replace("\xa0", " ")
    match = re.match(r"^(\d+)\.\s*(.*)$", raw_line)
    if match:
        entry_idx = int(match.group(1))
        content = match.group(2).strip()
    else:
        entry_idx = None
        content = raw_line

    parts = [p.strip() for p in content.split(",", 3)]

    raw_date = parts[0] if len(parts) > 0 else ""
    event_token = parts[1] if len(parts) > 1 else ""
    location = parts[2] if len(parts) > 2 else ""
    body = parts[3] if len(parts) > 3 else ""

    body = segment_census_household(body)

    return {
            "record_type": "census",
            "entry_idx": entry_idx,
            "date": raw_date,
            "tag": event_token,
            "location": location,
            "members": body,
        }

def segment_census_household(body: str) -> List[str]:
    return [member.strip() for member in body.split(" - ") if member.strip()]

"""
def parse_member(member: str, year: int) -> List[str]:
    name_regex = r"\b[A-ZÆØÅ][\wæøå]*(?:\s+(?:(?:f\.|v\.|von|van|de|la|de\s+la|den\s+ældre|den\s+yngre)\s+)*[A-ZÆØÅ][\wæøå]*){0,6}\b"
    status_regex = r"(.*)\b((?:u?gift|enke|fraskilt|separeret|i \d\.? ægteskab)[^()]+?)(?=\()"
    age1845 = re.findall(r"~(\d{4})\b", member)
    age = re.findall(r"\((\d{1,3})", member)
    name_match = re.match(name_regex, member)
    name, marital_status = "", "ugift"
    marital_match = re.findall(status_regex, member)
    birthplace = ""
    birthplace_match = re.findall(r"(?:\d{4} i|paa) (.+)\)", member)
    birthyear = 0
    if age:
        birthyear = year-int(age[0])
    if age1845:
        birthyear = age1845[0]
    if name_match:
        name = name_match[0]
    if marital_match:
        marital_status = marital_match[-1]
    if birthplace_match:
        birthplace = birthplace_match[-1]
    without_age = re.sub(r"\(.*", "(", member)
    without_name = re.sub(name_regex, "", without_age)
    without_marriage = re.sub(status_regex, r"\1", without_name)
    info = re.sub(r"\(", "", without_marriage)
    if "enke" in marital_status:
        print("\n\nInfo:")
        print(name)
        print(marital_status)
        print(birthyear)
        print(birthplace)
        print(info.strip())
"""


if __name__ == "__main__":
    census_f = open("proof_of_concept_data/askø_ft.dk.in", "r")
    church_f = open("proof_of_concept_data/askø.dk.in", "r")
    census_filelines = census_f.readlines()
    church_filelines = church_f.readlines()
    with open("proof_of_concept_data/askø_output.jsonl", "w") as output_f:
        for line in church_filelines:
            if not line.strip():
                continue
            payload = parse_church_record(line)
            output_f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        for line in census_filelines:
            if not line.strip():
                continue
            census_parsed = parse_record_header(line)
            output_f.write(json.dumps(census_parsed, ensure_ascii=False) + "\n")

        

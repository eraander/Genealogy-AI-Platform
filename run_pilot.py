import json, re
import instructor
from dotenv import load_dotenv
from typing import List, Tuple, Dict
from openai import OpenAI
from sqlalchemy.orm import RelationshipDirection
from extract_relations import SCHEMA_DISPATCHER, get_validation_context, Entity, BirthRecordExtraction, Relation, WitnessSpanExtraction, CensusMember

load_dotenv()

COMPLEX_WITNESS_EXTRACTION_PROMPT = """You are an archival information extraction engine for 18th/19th-century Danish parish registers.
Extract all distinct individuals, explicit interpersonal relations, and local locations from the provided witness clause.

### 1. Entity Classification & Active Witness Rules
- Head of Phrase (Active): The primary person standing witness MUST have is_active_witness=True.
  - In "Hans Løjets hustru Maren Jensdatter Muule", Maren is active.
  - In "Niels Hansens søn Jens", Jens is active.
  - In "Maren Sl. Laurids Madsens", Maren is active.
- Coordinated Individuals (Both Active): When joined by "og", "samt", or "med", ALL listed individuals are standing witness (is_active_witness=True).
  - In "Hans Hansen og hustru", BOTH Hans Hansen and his hustru are is_active_witness=True.
- Identifying Anchors (Inactive): A person mentioned purely to identify someone else (preceding genitive -s, or marked Sl./Salig) MUST have is_active_witness=False.
  - In "Hans Løjets hustru", Hans Løjet is is_active_witness=False.
  - In "Niels Hansens søn Jens", Niels Hansen is is_active_witness=False.

### 2. Name & Anchor Extraction Rules
- Explicit Personal Name: If a personal name exists for the witness, verbatim_name MUST contain that name (e.g., 'Maren Hansdatter Sl. Hans Rasmussen Bøttes' or 'Jens'). Never reduce a named individual to a title gloss.
- Unnamed Dependent: Only if NO personal name is given, keep the possessive phrase as verbatim_name (e.g., 'Hans Løjets hustru').
- Explicit Relational Trigger Required:
  - ONLY extract an anchor entity and relation if an explicit keyword is present:
    hustru, kone, enke, fæstemø(e), fæsteqvinde, søn, datter, bror, broder, søster, karl, pige, dreng, tjener.
  - Bare Genitives / Epithets WITHOUT a keyword (e.g., 'Sl. Hans Rasmussen Bøttes', 'Hr. Casten Drejers'): Do NOT extract as a separate entity or relation. Keep the entire phrase intact in verbatim_name.
- Anchor Cleaning: Strip trailing genitive '-s', '-es', '-ens' and prefixes like 'Sl.', 'Sal.', or 'Hr.' from the anchor's verbatim_name.

### 3. Relation Types & Strict Directionality
- SPOUSE_OF:
  - Connects married or betrothed persons (triggers: hustru, kone, enke, fæstemø, fæsteqvinde).
  - source_name: The dependent/witness (e.g., 'Margrethe Marie Olufsdatter' or 'Hans Løjets hustru').
  - target_name: The anchor spouse (e.g., 'Hans Løjet').
- PARENT_OF:
  - source_name MUST be the parent, target_name MUST be the offspring.
  - Example: "Niels Hansens søn Jens" -> source_name: 'Niels Hansen', relation_type: 'PARENT_OF', target_name: 'Jens'.
- EMPLOYED_BY:
  - For servants or apprentices (triggers: karl, pige, dreng, tjener).
  - source_name: The servant/dependent, target_name: The master/employer.

### 4. Location Extraction
- Set location_raw ONLY if an explicit geographic preposition is attached to the entity (e.g., 'paa Fejø' -> 'Fejø', 'af Oreby' -> 'Oreby').
- Otherwise, location_raw MUST be null. NEVER populate location_raw with person names, titles, or descriptions.

### Output JSON Format
Return a JSON object:
{
  "entities": [
    {
      "verbatim_name": string,
      "gender": "male" | "female" | null,
      "is_active_witness": boolean,
      "occupation_or_status": string | null,
      "location_raw": string | null
    }
  ],
  "relations": [
    {
      "source_name": string,
      "relation_type": "SPOUSE_OF" | "PARENT_OF" | "EMPLOYED_BY",
      "target_name": string
    }
  ]
}

### Few-Shot Examples

Input: "Maren Hansdatter Sl. Hans Rasmussen Bøttes /nu Bonde Jeppesens fæsteqvinde/"
Output:
{
  "entities": [
    {
      "verbatim_name": "Maren Hansdatter Sl. Hans Rasmussen Bøttes",
      "gender": "female",
      "is_active_witness": true,
      "occupation_or_status": "fæsteqvinde",
      "location_raw": null
    },
    {
      "verbatim_name": "Bonde Jeppesen",
      "gender": "male",
      "is_active_witness": false,
      "occupation_or_status": null,
      "location_raw": null
    }
  ],
  "relations": [
    {
      "source_name": "Maren Hansdatter Sl. Hans Rasmussen Bøttes",
      "relation_type": "SPOUSE_OF",
      "target_name": "Bonde Jeppesen"
    }
  ]
}

Input: "Niels Hansens søn Jens"
Output:
{
  "entities": [
    {
      "verbatim_name": "Jens",
      "gender": "male",
      "is_active_witness": true,
      "occupation_or_status": "søn",
      "location_raw": null
    },
    {
      "verbatim_name": "Niels Hansen",
      "gender": "male",
      "is_active_witness": false,
      "occupation_or_status": null,
      "location_raw": null
    }
  ],
  "relations": [
    {
      "source_name": "Niels Hansen",
      "relation_type": "PARENT_OF",
      "target_name": "Jens"
    }
  ]
}

Input: "Hans Hansen og hustru"
Output:
{
  "entities": [
    {
      "verbatim_name": "Hans Hansen",
      "gender": "male",
      "is_active_witness": true,
      "occupation_or_status": null,
      "location_raw": null
    },
    {
      "verbatim_name": "Hans Hansens hustru",
      "gender": "female",
      "is_active_witness": true,
      "occupation_or_status": "hustru",
      "location_raw": null
    }
  ],
  "relations": [
    {
      "source_name": "Hans Hansens hustru",
      "relation_type": "SPOUSE_OF",
      "target_name": "Hans Hansen"
    }
  ]
}

Input: "Hans Løjets hustru Maren Jensdatter Muule"
Output:
{
  "entities": [
    {
      "verbatim_name": "Maren Jensdatter Muule",
      "gender": "female",
      "is_active_witness": true,
      "occupation_or_status": "hustru",
      "location_raw": null
    },
    {
      "verbatim_name": "Hans Løjet",
      "gender": "male",
      "is_active_witness": false,
      "occupation_or_status": null,
      "location_raw": null
    }
  ],
  "relations": [
    {
      "source_name": "Maren Jensdatter Muule",
      "relation_type": "SPOUSE_OF",
      "target_name": "Hans Løjet"
    }
  ]
}

Input: "Hans Mortensen Krogs hustru paa Fejø"
Output:
{
  "entities": [
    {
      "verbatim_name": "Hans Mortensen Krogs hustru",
      "gender": "female",
      "is_active_witness": true,
      "occupation_or_status": "hustru",
      "location_raw": "Fejø"
    },
    {
      "verbatim_name": "Hans Mortensen Krog",
      "gender": "male",
      "is_active_witness": false,
      "occupation_or_status": null,
      "location_raw": "Fejø"
    }
  ],
  "relations": [
    {
      "source_name": "Hans Mortensen Krogs hustru",
      "relation_type": "SPOUSE_OF",
      "target_name": "Hans Mortensen Krog"
    }
  ]
}
"""

client = instructor.from_openai(OpenAI())

# 1. Relational nouns preceded by a genitive (-s, -ens, -es) or possessive/epithet
RELATIONAL_TRIGGERS = re.compile(
    r"""(?xi)
    (?:
        # Explicit genitive or definite/possessive context
        (?:[a-zæøå]+(?:s|ens|es)\s+|hans\s+|hendes\s+|sin\s+|deres\s+|sal(?:ig|\.)?\s+|sl\.\s+)
        (?:
            fæstemøe?|fæsteqvinde|fæstequinde|
            hustru(?:e)?|kone|enke|efterladte\s+enke|
            tjene(?:r|stefolk|stepige|stekarl)?|pige|karl|dreng|
            søn|datter|børn|broder|søster
        )
    )
    |
    # Standalone relational titles that imply an omitted or attached relation
    \b(?:efterladte\s+enke|sal\.\s+|sl\.\s+)\b
    """
)

# 2. Multi-entity coordination connectors
COORDINATION_TRIGGERS = re.compile(
    r"""(?xi)
    \s+(?:og|samp?t|\+|&|med\s+sin|med\s+hans|med\s+hendes)\s+
    """
)

LODGING_TRIGGERS = re.compile(
    r"""(?xi)
    \b(hos\s+)\s+
    """
)

def needs_secondary_pass(span: str) -> bool:
    return bool(RELATIONAL_TRIGGERS.search(span) or COORDINATION_TRIGGERS.search(span) or LODGING_TRIGGERS.search(span))

COLLECTIVE_LOC_RE = re.compile(
    r"""(?xi)
    \s*(?:,|og|samt)?\s*
    \b(?P<quant>alle|begge|samp?tlige?)\s+
    (?:af\s+(?P<loc>[A-ZÆØÅ][\w\s]+)|(?P<ibid>sammesteds|ibidem))\b\.?$
    """
)

EXPLICIT_LOC_RE = re.compile(
    r"""(?xi)
    \b(?:af|fra|i|paa|på)\s+
    (?P<loc>[A-ZÆØÅ][a-zæøå]+(?:\s+[A-ZÆØÅ][a-zæøå]+)*)\s*$
    """
)

IBID_RE = re.compile(r"\b(?:ibid\.?|ibidem|sammesteds)\b", re.IGNORECASE)

RELATIONS = {
    "barn" : "PARENT_OF",
    "kone" : "SPOUSE_OF",
    "fader" : "PARENT_OF",
    "moder" : "PARENT_OF",
    "søn" : "PARENT_OF",
    "datter" : "PARENT_OF",
    "broder" : "SIBLING_OF",
    "søster" : "SIBLING_OF"
}

def extract_census_members(members: List[str], current_id: int) -> Tuple[List[Entity], List[Relation]]:
    men, women = [], []
    relations, entities = [], []
    for member in members:
        birth_place_raw = ""
        age = ""
        birth_place_match = re.findall("\b{.*?}\b", member)
        age_match = re.findall(r"\(\d+\)", member)
        # print(age_match)
        if birth_place_match:
            birth_place_raw = birth_place_match[0]
            member = re.sub(birth_place_raw, "", member).strip()
        if age_match:
            age = age_match[0]
            member = re.sub(r"\(\d+\)", "", member).strip()
        parsed_member = member.split(" ; ")
        # print(parsed_member)
        if "mand " in parsed_member[1] + " " or "bonde " in parsed_member[1] + " ":
            entity = Entity(id=str(current_id), verbatim_name=parsed_member[0], is_unnamed=False, gender="male")
            men.append(entity)
            entities.append(entity)
            current_id += 1
        if "kone " in parsed_member[1] + " " or "madmoder " in parsed_member[1] + " ":
            entity = Entity(id=str(current_id), verbatim_name=parsed_member[0], is_unnamed=False, gender="female")
            women.append(entity)
            entities.append(entity)
            current_id += 1
            if "enke" not in parsed_member[-1] and men:
                spousal_relation = Relation(source_id=women[-1].id, target_id=men[-1].id, relation_type="SPOUSE_OF")
                relations.append(spousal_relation)
        if " barn " in parsed_member[1] + " " or " søn " in parsed_member[1] + " " or " datter " in parsed_member[1]:
            entity = Entity(id=str(current_id), verbatim_name=parsed_member[0], is_unnamed = False, gender="unknown")
            if " søn " in parsed_member[1]:
                entity.gender = "male"
            elif " datter " in parsed_member[1]:
                entity.gender = "female"
            entities.append(entity)
            current_id += 1
            if "deres " in parsed_member[1] or "sidste ægteskab" in parsed_member[1]:
                father_relation = Relation(source_id=men[-1].id, target_id=entity.id, relation_type="PARENT_OF")
                relations.append(father_relation)
                mother_relation = Relation(source_id=women[-1].id, target_id=entity.id, relation_type="PARENT_OF")
                relations.append(mother_relation)
            elif "hendes " in parsed_member[1]:
                mother_relation = Relation(source_id=women[-1].id, target_id=entity.id, relation_type="PARENT_OF")
                relations.append(mother_relation)
            elif "hans " in parsed_member[1]:
                father_relation = Relation(source_id=men[-1].id, target_id=entity.id, relation_type="PARENT_OF")
                relations.append(father_relation)
        if "tjeneste" in parsed_member[1] or "tjener" in parsed_member[1]:
            entity = Entity(id=str(current_id), verbatim_name=parsed_member[0], is_unnamed=False, gender="unknown")
            if "dreng" in parsed_member[1] or "karl" in parsed_member[1]:
                entity.gender = "male"
            elif "pige" in parsed_member[1]:
                entity.gender = "female"
            entities.append(entity)
            servant_relation = Relation(source_id=entity.id, target_id=men[-1].id if men else women[-1].id, relation_type="SERVANT_OF")
            relations.append(servant_relation)
            current_id += 1
    return entities, relations, current_id

def extract_complex_witness_span(span: str, client, model: str = "gpt-4o-mini") -> WitnessSpanExtraction:
    system_prompt = COMPLEX_WITNESS_EXTRACTION_PROMPT
    return client.chat.completions.create(
        model=model,
        response_model=WitnessSpanExtraction,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Witness Span:\n{span}"}
        ],
        temperature=0.0,
    )

def process_witnesses_in_order(
    raw_spans: List[str], 
    start_id: int,
    client=None
) -> Tuple[List[Entity], List[Relation], int]:
    current_id = start_id
    ordered_entities: List[Entity] = []
    accumulated_relations: List[Relation] = []

    if not raw_spans:
        return ordered_entities, accumulated_relations, current_id

    # 1. Inspect the terminal span for collective location ("alle af Askø")
    working_spans = list(raw_spans)
    last_span = working_spans[-1]
    tail_match = COLLECTIVE_LOC_RE.search(last_span)
    tail_directive = None

    if tail_match:
        tail_directive = {
            "quantifier": tail_match.group("quant").lower(),
            "location": tail_match.group("loc") or "Askø"
        }
        # Strip tail clause so it does not pollute the name
        working_spans[-1] = COLLECTIVE_LOC_RE.sub("", last_span).strip(" ,-")

    # 2. Sequential traversal: preserves exact text order
    for span in working_spans:
        clean_span = span.strip()
        if not clean_span:
            continue

        # Fast path: 1 span -> exactly 1 entity in place
        loc_match = EXPLICIT_LOC_RE.search(clean_span)
        explicit_loc = loc_match.group("loc") if loc_match else None

        if not needs_secondary_pass(clean_span):
            current_id += 1
            ordered_entities.append(
                Entity(
                    id=str(current_id),
                    verbatim_name=clean_span,
                    is_unnamed=False,
                    role="witness",
                    location_raw=explicit_loc
                )
            )
        else:
            # Secondary pass: 1 span -> N entities spliced directly in place
            extraction_result = extract_complex_witness_span(clean_span, client=client)
            
            # Map local names to new unique entity IDs for relation wiring
            name_to_id: Dict[str, str] = {}

            for w in extraction_result.entities:
                current_id += 1
                name_to_id[w.verbatim_name] = str(current_id)

                ordered_entities.append(
                    Entity(
                        id=str(current_id),
                        verbatim_name="[UNNAMED]" if not w.verbatim_name else w.verbatim_name,
                        is_unnamed=True if not w.verbatim_name else False,
                        gender=w.gender,
                        role="witness" if w.is_active_witness else "bystander",
                        occupation_or_status=w.occupation_or_status,
                        location_raw=w.location_raw if w.location_raw else explicit_loc
                    )
                )

            # Map the micro-pass relations to global IDs
            for rel in extraction_result.relations:
                s_id = name_to_id.get(rel.source_name)
                t_id = name_to_id.get(rel.target_name)
                if s_id and t_id:
                    accumulated_relations.append(
                        Relation(
                            source_id=s_id,
                            target_id=t_id,
                            relation_type=rel.relation_type,
                            qualifier=clean_span
                        )
                    )

    # 3. Backward location propagation over the assembled ordered list
    if tail_directive:
        max_hops = 2 if tail_directive["quantifier"] == "begge" else len(ordered_entities)
        hops = 0
        for ent in reversed(ordered_entities):
            if hops >= max_hops:
                break
            # Hard stop if an entity has an explicit location (e.g. 'af Oreby')
            if ent.location_raw:
                break
            ent.location_raw = tail_directive["location"]
            hops += 1

    return ordered_entities, accumulated_relations, current_id

def run_sample_batch(filepath: str, sample_limit: int = 5):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()][:sample_limit]
    # unique_num = 0
    current_id = 0
    for idx, record in enumerate(lines, 1):
        rec_type = record.get("record_type")
        schema = SCHEMA_DISPATCHER.get(rec_type)
        if not schema:
            continue
        if schema == BirthRecordExtraction:
            raw_context = get_validation_context(record)
            current_id += 1
            child = Entity(id=str(current_id), verbatim_name=record["child"], is_unnamed=False, gender=record["gender"], role="child")
            current_id += 1
            father = Entity(id=str(current_id), verbatim_name="[UNNAMED]" if not record["father"] else record["father"], is_unnamed=True if not record["father"] else False, gender="male", role="father")
            current_id += 1
            mother = Entity(id=str(current_id), verbatim_name="[UNNAMED]" if not record["mother"] else record["mother"], is_unnamed=True if not record["mother"] else False, gender="female", role="mother")
            witnesses, bystanders = [], []
            entities, relations, current_id = process_witnesses_in_order(record["witnesses"], current_id, client)
            # print(witnesses, relations, current_id)
            for entity in entities:
                if entity.role == "witness":
                    witnesses.append(entity)
                else:
                    bystanders.append(entity)

            try:
                """
                extraction = client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_model=schema,
                    max_retries=2,
                    context=raw_context,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                ...
                            )
                        },
                        {"role": "user", "content": f"Record:\n{raw_text}"}
                    ],
                    temperature=0.0,
                )
                """
                birth_record = BirthRecordExtraction(source_date_raw=record["date"], is_illegitimate=record["is_illeg"], location_raw=record["location"], tag=record["tag"], child=child, father=father, mother=mother, witnesses=witnesses, bystanders=bystanders, relations=[])
                child_parent_relations = [Relation(source_id=birth_record.father.id, target_id=birth_record.child.id, relation_type="PARENT_OF"),
                                        Relation(source_id=birth_record.mother.id, target_id=birth_record.child.id, relation_type="PARENT_OF") ]
                witness_relations = [Relation(source_id=witness.id, target_id=birth_record.child.id, relation_type="WITNESS_TO") for witness in witnesses]
                birth_record.relations.extend(child_parent_relations)
                birth_record.relations.extend(witness_relations)
                birth_record.relations.extend(relations)

                with open("sample_output.txt", "a") as f:
                    f.write(f"[{idx}] {rec_type.upper()} PASS: {birth_record.model_dump_json(indent=2)}\n")
            except Exception as e:
                print(f"[{idx}] {rec_type.upper()} REJECTED: {e}")
        else:
            entities, relations, current_id = extract_census_members(record["members"], current_id)
            print(entities)
            print(relations)
if __name__ == "__main__":
    # run_sample_batch("proof_of_concept_data/askø_output.jsonl", sample_limit=20)
    run_sample_batch("census_input.jsonl", sample_limit=25)
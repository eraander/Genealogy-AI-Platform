import json, re
import instructor
from dotenv import load_dotenv
from typing import List, Tuple
from openai import OpenAI
from extract_relations import SCHEMA_DISPATCHER, get_validation_context, Entity, BirthRecordExtraction, Relation, WitnessSpanExtraction

load_dotenv()

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

def extract_complex_witness_span(span: str, client, model: str = "gpt-4o-mini") -> WitnessSpanExtraction:
    system_prompt = (
        "You are an archival information extraction engine for 18th/19th century Danish parish records.\n"
        "Extract all distinct individuals and explicit interpersonal relations from the given witness clause.\n\n"
        "Crucial Rules for Possessive / Unnamed Phrases (e.g., '[Person A]s hustru', '[Person A]s karl'):\n"
        "1. You MUST extract TWO distinct entities:\n"
        "   - The anchor person (e.g. verbatim_name='Christian Andersen', is_active_witness=False).\n"
        "   - The unnamed dependent person (e.g. verbatim_name='Christian Andersens hustru', is_active_witness=True).\n"
        "2. You MUST emit the explicit relation connecting them:\n"
        "   - source_name: 'Christian Andersens hustru'\n"
        "   - relation_type: 'SPOUSE_OF'\n"
        "   - target_name: 'Christian Andersen'\n"
        "3. Preserve titles and status words with the entity (e.g. occupation_or_status='hustru').\n"
        "4. Exact naming rule: For the anchor, strip the genitive 's' (e.g., 'Christian Andersen', not 'Christian Andersens'). For the unnamed dependent, keep the full phrase 'Christian Andersens hustru'.\n"
    )

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

        if not needs_secondary_pass(clean_span):
            # Fast path: 1 span -> exactly 1 entity in place
            loc_match = EXPLICIT_LOC_RE.search(clean_span)
            explicit_loc = loc_match.group("loc") if loc_match else None

            current_id += 1
            ordered_entities.append(
                Entity(
                    id=str(current_id),
                    verbatim_name=clean_span,
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
                        verbatim_name=w.verbatim_name,
                        gender=w.gender,
                        role="witness",
                        occupation_or_status=w.occupation_or_status,
                        location_raw=w.location_raw
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
    unique_num = 0
    for idx, record in enumerate(lines, 1):
        rec_type = record.get("record_type")
        schema = SCHEMA_DISPATCHER.get(rec_type)
        if not schema:
            continue

        raw_context = get_validation_context(record)
        print(record)
        unique_num += 1
        child = Entity(id=str(unique_num), verbatim_name=record["child"], gender=record["gender"], role="child")
        unique_num += 1
        father = Entity(id=str(unique_num), verbatim_name=record["father"], gender="male", role="father")
        unique_num += 1
        mother = Entity(id=str(unique_num), verbatim_name=record["mother"], gender="female", role="mother")
        witnesses = []
        witnesses, relations, current_id = process_witnesses_in_order(record["witnesses"], unique_num+1, client)
        print(witnesses, relations, current_id)

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
            birth_record = BirthRecordExtraction(source_date_raw=record["date"], location_raw=record["location"], tag=record["tag"], child=child, father=father, mother=mother, witnesses=witnesses, relations=[])
            child_parent_relations = [Relation(source_id=birth_record.father.id, target_id=birth_record.child.id, relation_type="PARENT_OF"),
                                    Relation(source_id=birth_record.mother.id, target_id=birth_record.child.id, relation_type="PARENT_OF") ]
            # witness_relations = [Relation(source_id=witness.id, target_id=birth_record.child.id, relation_type="WITNESS_TO") for witness in witnesses]
            # birth_record.relations.extend(child_parent_relations)
            # birth_record.relations.extend(witness_relations)
            print(f"[{idx}] {rec_type.upper()} PASS: {birth_record.model_dump_json(indent=2)}")
        except Exception as e:
            print(f"[{idx}] {rec_type.upper()} REJECTED: {e}")

if __name__ == "__main__":
    run_sample_batch("proof_of_concept_data/askø_output.jsonl", sample_limit=5)
    run_sample_batch("proof_of_concept_data/askø_output.jsonl", sample_limit=5)
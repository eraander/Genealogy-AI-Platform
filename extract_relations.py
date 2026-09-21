import re
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, computed_field, ValidationInfo

# ---------------------------------------------------------------------------
# BASE ENTITY & SUBSTRING VALIDATOR
# ---------------------------------------------------------------------------

class Entity(BaseModel):
    """Base entity ensuring that all extracted spans exist verbatim in raw source text."""
    id: str = Field(description="Unique numerical identifier for the entity")
    gender: Optional[Literal["male", "female", "unknown"]] = None
    role: Literal["child", "father", "mother", "witness"]
    relational_notes: Optional[str] = Field(
        None,
        description="Any additional relational notes or context about the entity's relationship to other entities in the record."
    )
    verbatim_name: str = Field(
        description="Exact verbatim name/string as written in source text (e.g., 'Niels', 'Apollone Jeppesdatter'). "" if unnamed."
    )
    occupation_or_status: Optional[str] = Field(
        None, 
        description="Verbatim occupational cognomen or status (e.g., 'sognedegn', 'huusmand', 'ungkarl', 'enke')."
    )
    location_raw: Optional[str] = Field(
        None, 
        description="Verbatim origin or parish mention (e.g., 'Oreby', 'Fejø', 'Askø')."
    )

    @field_validator("verbatim_name", "occupation_or_status", "location_raw", mode="after")
    @classmethod
    def check_substring(cls, val: Optional[str], info: ValidationInfo) -> Optional[str]:
        if not val or not info.context:
            return val
        raw_text = info.context.get("raw_text", "")
        # Enforce exact verbatim presence in source slice
        if raw_text and (val in raw_text or f"{val}s" in raw_text or f"{val}es" in raw_text):
            return val
        if raw_text and val not in raw_text:
            raise ValueError(f"Span validation failure: '{val}' not found in '{raw_text}'")
        return val


class Relation(BaseModel):
    """Direct edge between two entities extracted within the same record."""
    source_id: str = Field(description="Unique id of source entity")
    relation_type: str = Field(
        description="""Relation type: 
        PARENT_OF: [source_name] parent of [target_name] (keywords: s.o., d.o., barn, søn, datter)
        SPOUSE_OF: [source_name] spouse of [target_name] (keywords: hustru, mand, kone), 
        WITNESS_TO: [source_name] witness to [target_name] (keywords: fadd., test., witnesses), 
        SPONSOR_OF: [source_name] sponsor of [target_name] (keywords: bar barnet), 
        SERVANT_OF: [source_name] servant of [target_name] (keywords: tjenestepige, tjenestekarl), 
        SIBLING_OF: [source_name] sibling of [target_name] (keywords: broder, søster)"""
    )
    target_id: str = Field(description="Unique id of target entity")
    qualifier: Optional[str] = Field(
        None, 
        description="Raw contextual evidence (e.g., 'd.o.', 's.o.', 'deres barn', 'hustru', 'fadd'. 'forl.')"
    )


# ---------------------------------------------------------------------------
# 1. BIRTH & BAPTISM RECORD SCHEMA (record_type == 'birth')
# ---------------------------------------------------------------------------

class BirthRecordExtraction(BaseModel):
    source_date_raw: str = Field(description="Verbatim date string as recorded in record")
    tag: str = Field(description="Tag to identify the event")
    # is_stillborn: bool = Field(default=False, description="True if marked dødfødt/dødfødde")
    is_illegitimate: bool = Field(default=False, description="True if marked uægte or illeg.")
    location_raw: str = Field(description="Verbatim location string as recorded in record")
    
    child: Entity
    father: Optional[Entity] = None
    mother: Optional[Entity] = None
    
    carrier: Optional[Entity] = Field(
        None, 
        description="Person carrying or holding child (e.g., 'bar barnet', 'susc.')"
    )
    witnesses: List[Entity] = Field(
        default_factory=list, 
        description="Godparents / witnesses listed under 'test.' or 'fadd.'"
    )
    relations: List[Relation] = Field(
        default_factory=list,
        description="Explicit graph edges (CHILD_OF, SPOUSE_OF, WITNESS_TO, etc.)"
    )

class ExtractedWitness(BaseModel):
    verbatim_name: str = Field(
        description="Verbatim text representing the person, including titles/epithets (e.g. 'Gaardmand Jens Hansen', 'Jens Hansens hustru Maren')."
    )
    gender: Optional[Literal["male", "female", "unknown"]] = None
    occupation_or_status: Optional[str] = Field(
        None, 
        description="Singularized status/occupation if explicitly stated or distributed (e.g., 'ungkarl', 'hustru', 'enke')."
    )
    location_raw: Optional[str] = Field(
        None, 
        description="Explicit origin mentioned directly for this person (e.g., 'Oreby'), otherwise None."
    )
    is_active_witness: bool = Field(
        default=True,
        description="False if the person is only referenced to identify someone else (e.g., the husband in 'Jens Hansens hustru Maren')."
    )

class InternalRelation(BaseModel):
    source_name: str = Field(description="verbatim_name of the subject entity")
    relation_type: Literal["SPOUSE_OF", "PARENT_OF", "CHILD_OF", "SERVANT_OF", "SIBLING_OF"]
    target_name: str = Field(description="verbatim_name of the object entity")

class WitnessSpanExtraction(BaseModel):
    entities: List[ExtractedWitness]
    relations: List[InternalRelation] = []

# ---------------------------------------------------------------------------
# 2. CONFIRMATION RECORD SCHEMA (record_type == 'confirmation')
# ---------------------------------------------------------------------------

class ConfirmationRecordExtraction(BaseModel):
    source_date_raw: str = Field(description="Verbatim date string as recorded in record")
    tag: str = Field(description="Tag to identify the event")
    candidate: Entity = Field(description="The youth being confirmed")
    father: Optional[Entity] = None
    mother: Optional[Entity] = None
    master_or_employer: Optional[Entity] = Field(
        None, 
        description="Master or employer if mentioned as servant (e.g., 'tjente hos Jeppe Rasmussen')"
    )
    age_raw: Optional[str] = Field(None, description="Raw age if recorded (e.g., '14 aar')")
    relations: List[Relation] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 3. MARRIAGE & BETROTHAL RECORD SCHEMA (record_type == 'marriage')
# ---------------------------------------------------------------------------

class MarriageRecordExtraction(BaseModel):
    source_date_raw: str = Field(description="Verbatim date string as recorded in record")
    tag: str = Field(description="Tag to identify the event")
    event_stage: str = Field(
        description="Event type: 'tr' (trolovelse/betrothal), 'm' (copulation/viede), 'lys' (lysning)"
    )
    groom: Entity
    bride: Entity
    groomsmen_bondsmen: List[Entity] = Field(
        default_factory=list, 
        description="Bondsmen/sponsors guaranteeing the marriage ('forl.')"
    )
    relations: List[Relation] = Field(
        default_factory=list,
        description="Kinship edges including bondsman relations (e.g., 'hendes fader Peder Hansen')"
    )


# ---------------------------------------------------------------------------
# 4. DEATH & BURIAL RECORD SCHEMA (record_type == 'death')
# ---------------------------------------------------------------------------

class DeathRecordExtraction(BaseModel):
    source_date_raw: str
    deceased: Entity
    age_raw: Optional[str] = Field(None, description="Verbatim age (e.g., '59 aar 6 m.', '11 hebd.')")
    associated_relative: Optional[Entity] = Field(
        None, 
        description="Relative anchoring identity (e.g., 's.o. Jeppe Hansen', 'Jens Løjets hustru')"
    )
    relative_relation_type: Optional[str] = Field(
        None, 
        description="Relationship to anchor: PARENT_OF, SPOUSE_OF, CHILD_OF"
    )
    relations: List[Relation] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# 5. CENSUS RECORD SCHEMA (record_type == 'census')
# ---------------------------------------------------------------------------

class CensusMember(BaseModel):

    member: Entity = Field(description="Entity node for the household member")
    census_year: Optional[int] = Field(None, exclude=True)
    # Verbatim captures directly from text
    age_raw: Optional[str] = Field(
        None, 
        description="Verbatim age string including parentheses if present, e.g. '(64)' or '64'"
    )
    birth_place_raw: Optional[str] = Field(
        None, 
        description="Verbatim birthplace including curly braces if present, e.g. '{Askø /Maribo Amt/}' or 'Askø /Maribo Amt/'"
    )
    occupation: Optional[str] = Field(None, description="Verbatim occupation if mentioned")
    position: Optional[str] = Field(
        None, 
        description="Verbatim role in household (e.g. 'hosbonde', 'hans kone', 'deres barn', 'tjenestekarl')"
    )
    marital_status_raw: Optional[str] = Field(
        None, 
        description="Verbatim marital condition (e.g. 'gift', 'ugift', 'enke 1ste gang')"
    )

    @field_validator("age_raw", "birth_place_raw", "occupation", "position", "marital_status_raw", mode="after")
    @classmethod
    def check_census_substrings(cls, val: Optional[str], info: ValidationInfo) -> Optional[str]:
        if not val or not info.context:
            return val
        raw_text = info.context.get("raw_text", "")
        if raw_text and val not in raw_text:
            raise ValueError(f"Span validation failure: '{val}' is not a verbatim substring of raw text.")
        return val

    # --- Normalized downstream properties ---

    @computed_field
    @property
    def age(self) -> Optional[int]:
        """Parses the numeric digits out of '(64)' or '64'."""
        if not self.age_raw:
            return None
        match = re.search(r"\b(\d+)\b", self.age_raw)
        return int(match.group(1)) if match else None

    @computed_field
    @property
    def clean_birth_place(self) -> Optional[str]:
        """Strips curly braces and extraneous whitespace from birthplace."""
        if not self.birth_place_raw:
            return None
        return self.birth_place_raw.strip("{} \t")

    @computed_field
    @property
    def estimated_birth_year(self) -> Optional[int]:
        """Calculates approximate birth year from census date and age."""
        if self.age is None or not self.census_year:
            return None
        return self.census_year - self.age

class CensusRecordExtraction(BaseModel):
    source_date_raw: str = Field(description="Census year or header date (e.g. '1 Feb 1845', '1 Jul 1787')")
    members: List[CensusMember] = Field(default_factory=list)
    relations: List[Relation] = Field(default_factory=list)

    @model_validator(mode="after")
    def get_census_year(self) -> "CensusRecordExtraction":
        """Parses the 4-digit census year from the household header and injects it into all members."""
        match = re.search(r"\b(1\d{3})\b", self.source_date_raw)
        year = int(match.group(1)) if match else None
        for m in self.members:
            m.census_year = year
        return self


# ---------------------------------------------------------------------------
# 6. DISPATCHER ROUTING HARNESS
# ---------------------------------------------------------------------------

SCHEMA_DISPATCHER = {
    "birth": BirthRecordExtraction,
    "confirmation": ConfirmationRecordExtraction,
    "marriage": MarriageRecordExtraction,
    "death": DeathRecordExtraction,
    "census": CensusRecordExtraction,
}

def get_validation_context(record: Dict[str, Any]) -> Dict[str, str]:
    """Flattens all strings and nested lists into a single corpus string for span checking."""
    tokens = []
    for v in record.values():
        if isinstance(v, list):
            tokens.extend([str(item) for item in v if item is not None])
        elif v is not None:
            tokens.append(str(v))
    return {"raw_text": " ".join(tokens)}
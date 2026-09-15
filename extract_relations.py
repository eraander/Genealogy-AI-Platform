from typing import List, Literal, Optional
from pydantic import BaseModel


class Entity(BaseModel):
    name: str
    role: Literal["child", "father", "mother", "carrier", "godparent", "groom", "bride", "groomsman", "deceased"]


class Relation(BaseModel):
    source: str
    type: Literal["child_of", "spouse_of", "carrier_for", "godparent_of", "groomsman_for"]
    target: str


class RecordPayload(BaseModel):
    record_type: Literal["birth", "marriage", "death", "confirmation", "introduction"]
    date_raw: str                       # e.g., "26 Jul 1761 (hjd. 29 Jul + bt. Dom XI p Trinit)"
    location: Optional[str] = None
    entities: List[Entity]
    relations: List[Relation]
    notes: Optional[str] = None
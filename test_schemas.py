import pytest
from extract_relations import (
    Entity, BirthRecordExtraction, DeathRecordExtraction, 
    CensusRecordExtraction, get_validation_context
)

RAW_BIRTH = {"record_type": "birth", "entry_idx": null, "date": "Dom Quinquag 1715 [3 Mar]", "tag": "bt", "location": "Askø sogn", "child_and_parents": "Apollone Jeppesdatter d.o. Jeppe Hansen", "witnesses": "test. Maren Hans Rasmussen Bøttes - Niels Jensen - Niels Jørgensen Grimmer - Jens Nielsen - Judith Jensdatter Muule - Karen Jensdatter", "notes": null}

RAW_DEATH = {"record_type": "death", "entry_idx": null, "date": "24 Nov 1714", "tag": "d/br", "location": "Askø sogn", "subject": "Anna Olufsdatter", "age": "85 aar", "extra_info": null}

RAW_CENSUS_1787 = {"record_type": "census", "entry_idx": 2, "date": "1 Jul 1787", "tag": "ft", "location": "Askø", "members": ["Ambrosius Løjet mand huusmand og tjener hos præsten i 1. ægteskab (56)", "Abelone Jørgensdatter hans kone i 1. ægteskab (48)", "Magdalene Løjet deres datter ugift (17)", "Birthe Rasmusdatter sig opholdende inderste og ernærer sig ved at spinde og giøre fiskegarn enke efter 1. ægteskab (60)"]}

RAW_CENSUS_1845 = {"record_type": "census", "entry_idx": 3, "date": "1 Feb 1845", "tag": "ft", "location": "Askø (en gaard)", "members": ["Hans Hansen kjøbmand gift (38) {Skaarup Sogn /Svendborg Amt/}", "Else Georgine Jensdatter hans kone gift (29) {Askø Sogn /Maribo Amt/}", "Jens Peter Christian Hansen deres barn (6) {Askø Sogn /Maribo Amt/}", "Ane Johanne Magdalene Hansen deres barn (2) {Askø Sogn /Maribo Amt/}", "Maren Mogensdatter pleiebarn (13) {Stokkemarke /Maribo Amt/}", "Peder Nielsen tjenestekarl ugift (38) {Stokkemarke /Maribo Amt/}", "Hans Rasmussen tjenestekarl ugift (23) {Femø /Maribo Amt/}", "Else Magdalene Pedersdatter tjenestepige ugift (21) {Askø /Maribo Amt/}", "Maren Lucie Nielsdatter tjenestepige ugift (28) {Askø /Maribo Amt/}"]}

parsed_c1845 = CensusRecordExtraction.model_validate({
    "source_date_raw": "1 Feb 1845",
    "members": [
        {"member": {"verbatim_name": "Hans Hansen", "occupation_or_status": "kjøbmand"}, "age_raw": "(38)", "birth_place_raw": "{Skaarup Sogn /Svendborg Amt/}", "marital_status_raw": "gift"},
        {"member": {"verbatim_name": "Else Georgine Jensdatter"}, "age_raw": "(29)", "birth_place_raw": "{Askø Sogn /Maribo Amt/}", "position": "hans kone", "marital_status_raw": "gift"},
        {"member": {"verbatim_name": "Jens Peter Christian Hansen"}, "age_raw": "(6)", "birth_place_raw": "{Askø Sogn /Maribo Amt/}", "position": "deres barn"},
        {"member": {"verbatim_name": "Ane Johanne Magdalene Hansen"}, "age_raw": "(2)", "birth_place_raw": "{Askø Sogn /Maribo Amt/}", "position": "deres barn"}
    ],
    "relations": [
        {"source_name": "Hans Hansen", "relation_type": "SPOUSE_OF", "target_name": "Else Georgine Jensdatter", "qualifier": "hans kone"},
        {"source_name": "Hans Hansen", "relation_type": "PARENT_OF", "target_name": "Jens Peter Christian Hansen", "qualifier": "deres barn"},
        {"source_name": "Else Georgine Jensdatter", "relation_type": "PARENT_OF", "target_name": "Jens Peter Christian Hansen", "qualifier": "deres barn"},
        {"source_name": "Else Georgine Jensdatter", "relation_type": "PARENT_OF", "target_name": "Ane Johanne Magdalene Hansen", "qualifier": "deres barn"},
        {"source_name": "Hans Hansen", "relation_type": "PARENT_OF", "target_name": "Ane Johanne Magdalene Hansen", "qualifier": "deres barn"}
    ]
})


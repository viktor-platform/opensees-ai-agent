
import json

from math import sqrt
from pathlib import Path
from collections import defaultdict
from typing import Annotated, DefaultDict

from app.types import CrossSectionInfo, LinesDict, MembersDict, CrossSectionsDict, NodesDict
from functools import lru_cache

def load_sections() -> dict[Annotated[str, "HollowSection, Ishape, PFC"], list[CrossSectionInfo]]:
    file_path = Path.cwd() / "app" / "db" / "sections.json" 

    with open(file_path) as jsonfile:
        data = json.load(jsonfile)
    return data

@lru_cache(maxsize=1)
def load_sections_db() -> CrossSectionsDict:
    """ sections.json: has cross section grouped by type  {HollowSection, Ishape, PFC}"""
    grouped_cs_dict: dict[Annotated[str, "HollowSection, Ishape, PFC"], list[CrossSectionInfo]] = load_sections()

    cross_section_dict: CrossSectionsDict = {}
    for values in grouped_cs_dict.values():
        for cs in values:
            cross_section_dict[cs["id"]] = cs
    
    return cross_section_dict

def create_members(
    lines: LinesDict,
    truss_diag_cs: int | None = None,
    column_cs: int | None = None,
    joist_cs: int | None = None,
    beam_cs: int | None = None,
    truss_chord_cs: int | None = None,
) -> MembersDict:
    cs_map: dict[str, int | None] = {
        "Truss Diagonal": truss_diag_cs,
        "Column":         column_cs,
        "Joist":          joist_cs,
        "Beam":           beam_cs,
        "Truss Chord":    truss_chord_cs,
    }

    members: MembersDict = {}
    for line in lines.values():
        line_type = line["Type"]
        if line_type not in cs_map:
            raise ValueError(f"Unknown line Type: {line_type!r}")

        cs = cs_map.get(line_type)
        if cs:
            members[line["id"]] = {
                "line_id":          line["id"],
                "cross_section_id": cs,
                "material_name":    "Steel",
            }
        else:
            raise ValueError(f"{line_type=} not in {cs_map=} ")
    return members

def calculate_weights_schedule(
    members: MembersDict,
    lines: LinesDict,
    nodes: NodesDict
) -> dict[str, float]:
    """
    Returns a mapping from each line Type to the total weight of its members.
    """
    cs_dict: CrossSectionsDict = load_sections_db()
    weights_by_type: DefaultDict[str, float] = defaultdict(float)

    for member in members.values():
        line = lines[member["line_id"]]
        nI = nodes[line["Ni"]]
        nJ = nodes[line["Nj"]]

        # Compute actual member length
        dx = nI["x"] - nJ["x"]
        dy = nI["y"] - nJ["y"]
        dz = nI["z"] - nJ["z"]
        length = sqrt(dx*dx + dy*dy + dz*dz)

        cs_info = cs_dict[member["cross_section_id"]]
        area = cs_info["A"]  # in mm²

        weight = area * length * (7.85e-6) # kg
        weights_by_type[line["Type"]] += weight

    return dict(weights_by_type)
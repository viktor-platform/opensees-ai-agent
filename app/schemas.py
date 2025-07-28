from pydantic import BaseModel, Field
from typing import Any
from dataclasses import dataclass
from app.db.members import load_sections_db


class PlatformInputs(BaseModel):
    xLenght: float = Field(..., description="Length around x axis")
    yLenght: float = Field(..., description="Length around y axis")
    height: float = Field(..., description="Platform height")
    nJoist: int = Field(..., description="Inital Joist number")
    distLoad: float = Field(..., description="Load distribution in kPa")

class PlatformMixedInputs(PlatformInputs):
    TrussDir: str = Field(..., description="Axis in which the truss will be created `y` or `x` Default is alwas x")
    TrussDepth: float = Field(..., description="Truss Depth")

class SectionSeed(BaseModel):
    column_cs: int = Field(description="Id of columns, default is the id=25 for UC 356x368x153")
    beam_cs: int = Field(description="Id of beams cross section, default is id=18 the id for UB 406x178x54")
    joist_cs: int = Field(description="Id of joist cross section, default is id=14 the id for UB 203x133x30")

class SectionSeedMixed(SectionSeed):
    truss_chord_cs: int =  Field(description="Id of truss chord, default is the id=1 for SHS 50 x 50 x 1.6")
    truss_diag_cs: int = Field(description="Id of truss diagh, default is the id=1 for SHS 50 x 50 x 1.6")



@dataclass
class DesignResult:
    inputs: PlatformInputs
    sections: SectionSeed
    max_disp_by_type: dict[str, float]
    weight_dict: dict[str, float]

    @property
    def total_weight(self) -> float:
        return sum(self.weight_dict.values())

    @property
    def global_max_disp(self) -> float:
        return min(self.max_disp_by_type.values()) if self.max_disp_by_type else 0.0
    
    @property
    def section_names(self) -> dict[str, str]:
        """Returns a dictionary of section types and their formatted names."""
        cross_section_map = load_sections_db()
        section_data = self.sections.model_dump() # Use .model_dump() for Pydantic
        names = {}
        for section_type_key, section_id in section_data.items():
            display_key = section_type_key.replace('_cs', '').replace('_', ' ').title()
            section_name = cross_section_map.get(section_id, {}).get("name", f"ID: {section_id}")
            names[display_key] = section_name
        return names
    
    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, DesignResult):
            return NotImplemented
        return self.total_weight < other.total_weight

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, DesignResult):
            return NotImplemented
        return self.total_weight == other.total_weight
    
    def __repr__(self):
        
        sections_used = []
        cross_section_dict = load_sections_db()

        for eletype, cross_section_id in self.sections.model_dump().items():
            if cross_section_id:
                sections_used = [f"{eletype}={cross_section_dict[cross_section_id]['name']}" ]
            
        return f"<DesignResult(max_disp={self.global_max_disp}, total_weight={self.total_weight}, sections={sections_used})>"
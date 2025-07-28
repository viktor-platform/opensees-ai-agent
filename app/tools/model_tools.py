from app.schemas import PlatformInputs, PlatformMixedInputs, SectionSeed, SectionSeedMixed
from app.geometry.platform import Platform, PlatformMixed
from app.db.members import create_members, load_sections_db
from app.types import NodesDict, LinesDict, MembersDict

def generate_model_inputs(inputs: PlatformInputs | PlatformMixedInputs, sections: SectionSeedMixed | SectionSeed) -> tuple[NodesDict, LinesDict, MembersDict, float]:
    
    platform: Platform | PlatformMixed
    
    if isinstance(inputs, PlatformMixedInputs) and isinstance(sections, SectionSeedMixed):
        platform = PlatformMixed(
            xLenght=inputs.xLenght, yLenght=inputs.yLenght, height=inputs.height, 
            nJoist=inputs.nJoist, TrussDepth=inputs.TrussDepth, TrussDir=inputs.TrussDir, nDivision=7
        )


    elif isinstance(inputs, PlatformInputs) and isinstance(sections, SectionSeed):
        platform = Platform(
            xLenght=inputs.xLenght, yLenght=inputs.yLenght, height=inputs.height, 
            nJoist=inputs.nJoist, nDivision=7
        )
    else:
        raise ValueError("Geometry should be either PlatformMixedInputs or Platform")

    # Generate node lines based on the type of the model!
    nodes, lines = platform.create_model()     
    members = create_members(lines=lines, **sections.model_dump())
    return nodes, lines, members, inputs.distLoad

def get_cross_section_library() -> str:
    cs: dict[int, MembersDict] = load_sections_db()
    return "".join(f"id:{key}: name:{section["name"]}" for key, section in cs.items())

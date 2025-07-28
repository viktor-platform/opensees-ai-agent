import json
import itertools
import viktor as vkt

from typing import overload
from app.geometry.platform import Platform, PlatformMixed
from app.db.members import load_sections_db, calculate_weights_schedule, load_sections
from app.opensees.model import Model, calculate_displacements
from app.schemas import PlatformMixedInputs, PlatformInputs, SectionSeed, SectionSeedMixed, DesignResult
from app.tools.model_tools import generate_model_inputs
from app.types import steel_cost

AnyPlatform = Platform | PlatformMixed

def calculate_model(inputs: PlatformInputs | PlatformMixedInputs, sections: SectionSeed):
    cs_dict = load_sections_db()

    nodes, lines, members, dist_load = generate_model_inputs(inputs=inputs, sections=sections)
    
    nodesWithLoad = list({node for line in lines.values() if line.get("Type") == "Joist" for node in (line["Ni"], line["Nj"])})
    loadableArea = (inputs.xLenght/1000) * (inputs.yLenght / 1000)
    load = dist_load * loadableArea * 1000
    nodalLoadMagnitud = load / len(nodesWithLoad) if nodesWithLoad else 0
    
    my_model = Model(
        nodes=nodes, lines=lines, cross_sections=cs_dict, members=members,
        nodesWithLoad=nodesWithLoad, nodalLoadMagnitud=nodalLoadMagnitud
    )
    my_model.create_model()
    my_model.run_model() 
    
    max_disp_by_type, disp_dict = calculate_displacements(lines=lines, nodes=nodes)
    weight_dict = calculate_weights_schedule(members=members, lines=lines, nodes=nodes)
    return nodes, lines, members, max_disp_by_type, disp_dict, weight_dict

@overload
def generate_combinations(inputs: PlatformMixedInputs) -> list[tuple[int, int, int, int, int]]: ...
@overload
def generate_combinations(inputs: PlatformInputs) -> list[tuple[int, int, int]]: ...

def generate_combinations(inputs: PlatformInputs | PlatformMixedInputs):
    cross_section_dict = load_sections()
    i_shape_ids = [cs["id"] for cs in cross_section_dict["Ishape"]]
    joist_number = [3, 5, 6, 7, 8, 9]
    pfc_sections_ids = [cs["id"] for cs in cross_section_dict["PFC"]]
    beam_sections = i_shape_ids
    joist_sections = i_shape_ids + pfc_sections_ids

    if isinstance(inputs, PlatformMixedInputs):
        truss_depth_range = list(range(700, 1501, 400))
        hollow_section_ids = [cs["id"] for cs in cross_section_dict["HollowSection"]]
        truss_chord_sections = hollow_section_ids
        combinations = list(itertools.product(beam_sections, joist_sections, joist_number, truss_depth_range, truss_chord_sections))
        return combinations
    else:
        combinations = list(itertools.product(beam_sections, joist_sections, joist_number))
        return combinations

def run_optimization(seed: PlatformInputs | PlatformMixedInputs) -> list[DesignResult]:
    """
    Runs a unified optimization loop for both standard and mixed platforms.
    """
    results: list[DesignResult] = []
    if isinstance(seed, PlatformMixedInputs):
        combinations = generate_combinations(seed)
        for i, combo in enumerate(combinations):
            beam_sec, joist_sec, joist_number, truss_depth, truss_section = combo

            current_inputs = seed.model_copy(deep=True)
            current_inputs.nJoist = joist_number
            current_inputs.TrussDepth = truss_depth
            
            sections = SectionSeedMixed(
                column_cs=25, beam_cs=beam_sec, joist_cs=joist_sec,
                truss_chord_cs=truss_section, truss_diag_cs=truss_section
            )
            nodes, lines, members, max_disp_by_type, disp_dict, weight_dict = calculate_model(inputs=current_inputs, sections=sections)
            results.append(DesignResult(inputs=current_inputs, sections=sections, max_disp_by_type=max_disp_by_type, weight_dict=weight_dict))
                    

    
    elif isinstance(seed, PlatformInputs):
        combinations = generate_combinations(seed)
        for i, combo in enumerate(combinations):
            beam_sec, joist_sec, joist_number = combo
            
            current_inputs = seed.model_copy(deep=True)
            current_inputs.nJoist = joist_number
            
            sections = SectionSeed(
                column_cs=25, beam_cs=beam_sec, joist_cs=joist_sec
            )
            nodes, lines, members, max_disp_by_type, disp_dict, weight_dict = calculate_model(inputs=current_inputs, sections=sections)
            results.append(DesignResult(inputs=current_inputs, sections=sections, max_disp_by_type=max_disp_by_type, weight_dict=weight_dict))
    return results


def store_design_results_as_table(design_results: list[DesignResult]):
    """
    Converts a list of DesignResult objects into a simple table structure (headers and data),
    and stores it as a JSON in vkt.Storage.
    """
    if not design_results:
        table_structure = {"headers": [], "data": []}
    else:
        
        first_result_sections = list(design_results[0].section_names.keys())
        headers = ["Total Weight (kg)","Max Displacement (mm)","Total Cost (€)", "# Joist"] + first_result_sections

        data = []
        for result in design_results:
            row = [
                round(result.total_weight, 2),
                round(result.global_max_disp, 4),
                round(result.total_weight*steel_cost,2),
                round(result.inputs.nJoist)
            ]
            row.extend(result.section_names.values())
            
            data.append(row)
        
        table_structure = {"headers": headers, "data": data}

    vkt.Storage().set(
        "optimization_table",
        data=vkt.File.from_data(json.dumps(table_structure).encode()),
        scope="entity",
    )

def last_optimization_result(max_models: int = 10) -> str:
    """
    Return up to `max_models` results as plain text.
    The first data row is the best model.
    """
    try:
        raw = vkt.Storage().get("optimization_table", scope="entity").getvalue()
        table = json.loads(raw)

        headers = table.get("headers", [])
        all_rows = table.get("data", [])

        if not headers or not all_rows:
            return "No optimization results available"

        rows = all_rows[: max_models]

        lines = [", ".join(map(str, headers))]
        for row in rows:
            lines.append(", ".join(map(str, row)))

        print(lines)
        return "Optimal model is in the first row\n" + "\n".join(lines)

    except Exception:
        return "No optimization results available"
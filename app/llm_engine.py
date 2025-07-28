import logging
import pprint
import instructor
import plotly.graph_objects as go

from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ParsedChatCompletion
from typing import Union
from textwrap import dedent

from app.tools.analysis_tools import run_optimization, calculate_model, store_design_results_as_table, last_optimization_result
from app.tools.model_tools import generate_model_inputs, get_cross_section_library
from app.schemas import PlatformInputs, SectionSeed, SectionSeedMixed, PlatformMixedInputs
from app.db.members import load_sections_db
from app.plots.model_defo import plot_deformed_mesh
from app.plots.model_viz import plot_3d_model

logger = logging.getLogger(__name__)
load_dotenv()
client = instructor.from_openai(OpenAI())

class PlotPlatform(BaseModel):
    geometry: PlatformInputs = Field(..., description="Instance of PlatformInputs")
    sections: SectionSeed = Field(..., description= "Use default cs seection they are typical in the user organization")

class PlotPlatformMixed(BaseModel):
    geometry: PlatformMixedInputs = Field(..., description="Instance od PlatformMixedInputs (with truss)")
    sections: SectionSeedMixed = Field(..., description= "Use default cs seection they are typical in the user")

class OptimizationTool(BaseModel):
    deformation_limit: float = Field(..., description="Deformation limit to be used in the optimizatin process")
    geometry: Union[PlatformInputs, PlatformMixedInputs] =  Field(..., description="Define this based on the type of the structure to be runned or analyzed. Use this to run or analyze the model and show the result to the user, tell him the optimal model will be display along a table with the complete analzed models")

class RunModelTool(BaseModel):
    previous_geometry: Union[PlatformInputs, PlatformMixedInputs] = Field(..., description="Using the same inputs used in PlotPlatform or  PlotPlatformMixed")
    sections: Union[SectionSeed, SectionSeedMixed]  = Field(..., description="Use SectionSeed for simple Platform and SectionSeedMixed with PlatformMixed")

class Response(BaseModel):
    response: str = Field(..., description="Be conversational firendly and Format the response always nicely")
    selected_tool: Union[None , RunModelTool, PlotPlatform, PlotPlatformMixed, OptimizationTool] = Field(..., description="Select any of these tools,  PlotPlatform, PlotPlatformMixed to create and displaye the modes, RunModel to analuze and show deformatinos, and Optimization to optimize   otherwise return None")


def llm_response(conversation_history: list[dict],
                 verbose: bool = True) -> ParsedChatCompletion[Response]:
    
    messages = []
    # Default system prompt is always first
    system_message = {
        "role": "system",
        "content": dedent(
            f"""
            You are a helpful assistant with the following context, who formats responses clearly and helps users create and optimize structural models in OpenSees.

            Respond by describing the functionality of the tools you have, without mentioning their names explicitly.

            You can create two types of platforms. The first type uses only elements with open sections, such as I-shaped beams or PFC (C/U-shaped steel sections). You have a tool designed to generate this type of structure.

            The second type of platform uses truss bearers to support the joists. These truss elements — including diagonals, top, and bottom chords — are modeled using hollow sections.

            Your mission is to interact with the user and assist in optimizing the platform configuration.

            In the first interaction, inform the user that you can help them optimize the platform. Then, naturally ask them to provide the platform specifications. By default, use the plotting tool to create and display the platform.

            **Important**: Every time `selected_tool` is not `None`, the VIKTOR app will render the model with the specified inputs. You may say something like, “The structure will be rendered on the right-hand side of the application.”

            All units are in millimeters.
            Do not optimize the structure yourself use OptimizationTool
            **
            This are the available cross Sections{get_cross_section_library()}
            **
            This is the infromation about the latest optimize models {last_optimization_result()}
            """
        )
    }
    messages.append(system_message)
    messages.extend(conversation_history)
    if verbose:
        logger.debug("Request messages:\n%s", pprint.pformat(messages))
    
    resp_chunks = client.chat.completions.create_partial(
        model="gpt-4.1",
        messages=messages,
        response_model=Response,
        temperature=0.3,
    )

    resp_final = None
    # Streaming
    for resp in resp_chunks:
        if verbose:
            logger.debug("Received response chunk:\n%s", resp)
        resp_final: Response = resp 

    return resp_final


def execute_tool(response: Response) -> tuple[str, go.Figure | None]:
    """Exectue the tools based on the user query and file_content. Generates a text response
    or a Plotly view."""
    print(f"[Debug] {response}")
    if isinstance(response.selected_tool, PlotPlatform) or isinstance(response.selected_tool, PlotPlatformMixed):
        inputs = response.selected_tool.geometry
        sections = response.selected_tool.sections
        nodes, lines, members, _ = generate_model_inputs(inputs=inputs, sections=sections)
        cs_dict = load_sections_db()
        fig = plot_3d_model(nodes, lines, members, cs_dict)
        return response.response, fig

    if isinstance(response.selected_tool, RunModelTool):
        modeltype = response.selected_tool.previous_geometry
        sections = response.selected_tool.sections
        nodes, lines, members, max_disp_by_type, disp_dict, weight_dict = calculate_model(inputs=modeltype, sections=sections)
        cs_dict = load_sections_db()
        fig = plot_deformed_mesh(disp_dict=disp_dict, members=members, cross_sections= cs_dict, nodes=nodes, lines=lines)
        return response.response, fig

    if isinstance(response.selected_tool, OptimizationTool):
        modeltype = response.selected_tool.geometry
        limit= response.selected_tool.deformation_limit
        design_results = run_optimization(seed=modeltype)
        valid_designs = [design for design in sorted(design_results) if abs(design.global_max_disp) < limit]
        store_design_results_as_table(valid_designs)
        sections = valid_designs[0].sections
        modeltype = valid_designs[0].inputs
        nodes, lines, members, max_disp_by_type, disp_dict, weight_dict = calculate_model(inputs=modeltype, sections=sections)
        cs_dict = load_sections_db()
        fig = plot_deformed_mesh(disp_dict=disp_dict, members=members, cross_sections= cs_dict, nodes=nodes, lines=lines)
        return response.response, fig
            
    return response.response, None
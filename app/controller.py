import os
import json
import viktor as vkt
import plotly.graph_objects as go

from openai import OpenAI
from dotenv import load_dotenv
from app.llm_engine import llm_response, execute_tool
from app.plots.model_viz import default_blank_scene
from typing import Literal
from textwrap import dedent

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_visibility(params, **kwargs):
    if not params.chat:
        entities = vkt.Storage().list(scope="entity")
        for entity in entities:
            if entity == "optimization_table":
                vkt.Storage().delete("optimization_table", scope="entity")

    try:
        vkt.Storage().get("optimization_table", scope="entity").getvalue()
        return True
    except Exception:
        # If there is no data, then view is hiden.
        return False


def store_scene(figure: go.Figure, view_name: Literal["view"] = "view") -> None:
    """This function stores the output of a tool call in
    the vkt.Storage object. The storage object can be used to communicate
    between views."""
    vkt.Storage().set(
        view_name,
        data=vkt.File.from_data(figure.to_json().encode()),
        scope="entity",
    )


class Parametrization(vkt.Parametrization):
    appText = vkt.Text(
        dedent(
            """
            # OpenSees AI Agent

            Create, analyze, and optimize steel platforms in one chat. Tweak loads, geometry, or sections and see updated results instantly.
            """
        )
    )
    chat = vkt.Chat("", method="call_llm")


class Controller(vkt.Controller):
    parametrization = Parametrization()

    def call_llm(self, params, **kwargs) -> vkt.ChatResult | None:
        """Multi-turn conversation between the user and the agent."""
        # Get conversation
        conversation_history = params.chat.get_messages()
        #  Check if user uploaded an Excel Field
        if conversation_history:
            response = llm_response(
                conversation_history=conversation_history,
            )

            if response:
                llm_message, fig = execute_tool(response)
                if fig:
                    store_scene(fig)
                    get_visibility(params, **kwargs)

                return vkt.ChatResult(params.chat, llm_message)
            else:
                raise ValueError("The LLM returned no parsed reponse.")
        return None

    @vkt.PlotlyView("Plotting Tool", width=100)
    def get_plotly_view(self, params, **kwargs) -> vkt.PlotlyResult:
        """This view plots the output of a tool call in a Plotly view.
        All tool calls are go.Figures exported as JSON. They are saved in
        Storage and retrieved here."""
        # 1. Delete tools calls from storage if there is no .xlsx file
        if not params.chat:
            entities = vkt.Storage().list(scope="entity")
            for entity in entities:
                if entity == "view":
                    vkt.Storage().delete("view", scope="entity")

        # 2. Try to get the previous view from the tool call, otherwise blank scene
        try:
            raw = vkt.Storage().get("view", scope="entity").getvalue()
            fig = go.Figure(json.loads(raw))
        except Exception:
            fig = default_blank_scene()

        return vkt.PlotlyResult(fig.to_json())

    @vkt.TableView("Results", visible=get_visibility)
    def design_results_view(self, params, **kwargs):
        get_visibility(params, **kwargs)
        try:
            # 1. Get the pre-formatted table data from storage
            raw_table_data = (
                vkt.Storage().get("optimization_table", scope="entity").getvalue()
            )
            table = json.loads(raw_table_data)

        except (FileNotFoundError, TypeError):
            # If no data is stored, show an empty table
            return vkt.TableResult(
                data=[], column_headers=["No results generated yet."]
            )

        # 2. Pass the headers and data directly to the result
        return vkt.TableResult(
            data=table.get("data", []), column_headers=table.get("headers", [])
        )
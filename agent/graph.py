"""
Assembles the LangGraph agent:

    START -> retrieve_evidence -> score_fit -> (route by score) one of:
        score >= ALERT_THRESHOLD   : draft_pitch -> mark_alert -> END
        score >= REVIEW_THRESHOLD  : flag_review -> END
        otherwise                  : discard -> END
"""
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from agent import settings
from agent.nodes import (
    retrieve_evidence, score_fit, draft_pitch, mark_alert, flag_review, discard,
)
from agent.routing import route_name


class AgentState(TypedDict, total=False):
    posting: dict
    evidence: list
    assessment: dict
    score: int
    pitch: str
    suggested_bullets: list
    decision: str


def _route(state: AgentState) -> str:
    return route_name(state["score"], settings.ALERT_THRESHOLD, settings.REVIEW_THRESHOLD)


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("retrieve_evidence", retrieve_evidence)
    g.add_node("score_fit", score_fit)
    g.add_node("draft_pitch", draft_pitch)
    g.add_node("mark_alert", mark_alert)
    g.add_node("flag_review", flag_review)
    g.add_node("discard", discard)

    g.add_edge(START, "retrieve_evidence")
    g.add_edge("retrieve_evidence", "score_fit")
    g.add_conditional_edges(
        "score_fit",
        _route,
        {"draft_pitch": "draft_pitch", "flag_review": "flag_review", "discard": "discard"},
    )
    g.add_edge("draft_pitch", "mark_alert")
    g.add_edge("mark_alert", END)
    g.add_edge("flag_review", END)
    g.add_edge("discard", END)

    return g.compile()

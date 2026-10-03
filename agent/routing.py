"""
The branch decision, kept as a pure function so it's trivially testable.
Returns the NAME OF THE NEXT GRAPH NODE.
"""


def route_name(score: int, alert_threshold: int, review_threshold: int) -> str:
    if score >= alert_threshold:
        return "draft_pitch"   # strong fit -> write a tailored pitch, then alert
    if score >= review_threshold:
        return "flag_review"   # maybe -> store for manual review, no alert
    return "discard"           # poor fit -> record and move on

"""Architecture decisions use stable IDs and the explicit owner acceptance path."""
from .projects import ProjectService


class Decisions(ProjectService):
    def propose_decision(self, text, *, source_ref, decision_id=None):
        return self.propose(text, kind="decision", source_ref=source_ref, fact_id=decision_id)

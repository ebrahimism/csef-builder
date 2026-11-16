"""Requirement and assumption proposals stay separate from accepted facts."""
from .projects import ProjectService


class Requirements(ProjectService):
    def propose_requirement(self, text, *, source_ref, fact_id=None):
        return self.propose(text, kind="requirement", source_ref=source_ref, fact_id=fact_id)

    def record_assumption(self, text, *, source_ref):
        return self.propose(text, kind="assumption", source_ref=source_ref)

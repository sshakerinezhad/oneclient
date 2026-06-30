from dataclasses import dataclass, field


@dataclass
class QueryResult:
    cypher: str
    rows: list[dict]
    error: str | None = None
    attempts: int = 1


@dataclass
class Evidence:
    request: str
    result: QueryResult


@dataclass
class OrchestratorState:
    question: str
    evidence: list[Evidence] = field(default_factory=list)
    iterations: int = 0

    @property
    def query_count(self) -> int:
        return len(self.evidence)

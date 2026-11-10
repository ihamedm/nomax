from pydantic import BaseModel, Field


class CategorySuggestionRequest(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


class CategorySuggestionDiagnosticRequest(CategorySuggestionRequest):
    """Admin-only probe. The overrides apply to one diagnostic run only."""

    rules_enabled: bool | None = None
    probe_laya: bool = True

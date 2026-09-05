from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class RunStage(StrEnum):
    REQUIREMENT = "requirement"
    SPECIFICATION = "specification"
    REVIEW_SPEC = "review_spec"
    COMPONENTS = "components"
    BINDING = "binding"
    ASSEMBLY = "assembly"
    LAYOUT_CHECK = "layout_check"
    REVIEW_FINAL = "review_final"
    FINISHED = "finished"
    BLOCKED = "blocked"
    FAILED = "failed"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConversationDecision(BaseModel):
    intent: Literal["chat", "design"]
    reply: str = Field(min_length=1, max_length=2_000)


class OpenPencilProfile(BaseModel):
    endpoint: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    output_file: str | None = None
    target_mode: Literal["new_file", "existing_file"] = "new_file"
    knowledge_id: Literal["auto", "shadcn-ui", "taptap"] = "auto"

    @field_validator("endpoint", "source_file", "output_file", mode="before")
    @classmethod
    def strip_profile_value(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("endpoint")
    @classmethod
    def validate_http_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("endpoint must be an absolute HTTP(S) URL")
        return value

    @model_validator(mode="after")
    def protect_component_source(self) -> "OpenPencilProfile":
        if (
            self.output_file
            and self.target_mode == "new_file"
            and self.source_file == self.output_file
        ):
            raise ValueError("output_file must differ from source_file in new_file mode")
        return self


class LayoutRule(BaseModel):
    mode: Literal["block", "flex", "grid", "absolute"] = "flex"
    direction: Literal["row", "column"] = "column"
    gap: int = Field(default=16, ge=0, le=128)
    columns: int | None = Field(default=None, ge=1, le=12)
    padding: int = Field(default=0, ge=0, le=160)


class ComponentRequirement(BaseModel):
    role: str
    variant_intent: str | None = None
    required_slots: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)


class UiNode(BaseModel):
    id: str
    kind: Literal["container", "component", "text", "media"]
    name: str
    content: dict[str, Any] = Field(default_factory=dict)
    layout: LayoutRule | None = None
    requirement: ComponentRequirement | None = None
    children: list["UiNode"] = Field(default_factory=list)


class UiSpecification(BaseModel):
    schema_version: Literal["2.0"] = "2.0"
    screen_name: str
    platform: Literal["mobile", "tablet", "desktop", "responsive"] = "responsive"
    viewport_width: int = Field(ge=320, le=2560)
    viewport_height: int = Field(ge=480, le=12000)
    summary: str
    root: UiNode


class ComponentCandidate(BaseModel):
    component_id: str
    library_id: str
    name: str
    path: str = ""
    canonical_path: str
    width: float | None = None
    height: float | None = None
    text_slots: list[str] = Field(default_factory=list)
    variant_name: str | None = None
    knowledge_score: int = 0


class ComponentBinding(BaseModel):
    node_id: str
    status: Literal["resolved", "unresolved"]
    component_id: str | None = None
    library_id: str | None = None
    canonical_path: str | None = None
    selected_variant: str | None = None
    text_values: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(default=0, ge=0, le=1)
    rationale: str = ""
    reason: str | None = None


class ComponentBindingSet(BaseModel):
    bindings: list[ComponentBinding]


class OpenPencilArtifact(BaseModel):
    document_id: str
    page_id: str
    page_name: str
    output_file: str
    root_node_id: str
    created_nodes: int
    share_url: str | None = None


class RunArtifacts(BaseModel):
    knowledge_snapshot: dict[str, Any] | None = None
    component_candidates: list[dict[str, Any]] = Field(default_factory=list)
    component_bindings: dict[str, Any] | None = None
    openpencil_artifact: dict[str, Any] | None = None
    layout_review: dict[str, Any] | None = None


class LayoutFinding(BaseModel):
    severity: Literal["info", "warning", "error"]
    category: str
    node_ids: list[str] = Field(default_factory=list)
    evidence: str
    correction: str


class LayoutReview(BaseModel):
    status: Literal["valid", "invalid"]
    summary: str
    findings: list[LayoutFinding] = Field(default_factory=list)


class SessionCreate(BaseModel):
    title: str = "Untitled session"


class SessionView(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class DesignSystemView(BaseModel):
    id: str
    name: str
    path: str
    knowledge_id: Literal["auto", "shadcn-ui", "taptap"] = "auto"


class RunCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=12_000)
    screen_name: str = Field(min_length=1, max_length=120)
    platform: Literal["mobile", "tablet", "desktop", "responsive"] = "responsive"
    library_ids: list[str] = Field(default_factory=list)
    mcp_profile: OpenPencilProfile | None = None


class RunView(BaseModel):
    id: UUID
    session_id: UUID
    revision: int
    prompt: str
    screen_name: str
    platform: str
    stage: RunStage
    status: RunStatus
    intent: Literal["chat", "design"] | None = None
    assistant_message: str | None = None
    library_ids: list[str]
    mcp_profile: OpenPencilProfile | None = None
    specification: UiSpecification | None = None
    error: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ReviewCreate(BaseModel):
    checkpoint: Literal["specification", "final"]
    decision: Literal["approved", "changes_requested", "rejected"]
    revision: int = Field(ge=1)
    feedback: str = Field(default="", max_length=4_000)
    mcp_profile: OpenPencilProfile | None = None


class RunRetry(BaseModel):
    mcp_profile: OpenPencilProfile | None = None


class WorkflowEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    revision: int
    sequence: int
    type: str
    time: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)


class Problem(BaseModel):
    code: str
    title: str
    detail: str
    retryable: bool = False
    action: str | None = None

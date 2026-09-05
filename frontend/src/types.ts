export type RunStage =
    | "requirement"
    | "specification"
    | "review_spec"
    | "components"
    | "binding"
    | "assembly"
    | "layout_check"
    | "review_final"
    | "finished"
    | "blocked"
    | "failed";

export interface Session {
    id: string;
    title: string;
    created_at: string;
    updated_at: string;
}

export interface LayoutRule {
    mode: "block" | "flex" | "grid" | "absolute";
    direction: "row" | "column";
    gap: number;
    columns?: number;
    padding: number;
}

export interface UiNode {
    id: string;
    kind: "container" | "component" | "text" | "media";
    name: string;
    content: Record<string, unknown>;
    layout?: LayoutRule;
    requirement?: {
        role: string;
        variant_intent?: string;
        required_slots: string[];
        capabilities: string[];
    };
    children: UiNode[];
}

export interface LayoutFinding {
    severity: "info" | "warning" | "error";
    category: string;
    node_ids: string[];
    evidence: string;
    correction: string;
}

export interface RunArtifacts {
    knowledge_snapshot?: { libraries?: string[]; strategy?: string };
    component_candidates: Record<string, unknown>[];
    component_bindings?: { bindings?: Record<string, unknown>[] };
    openpencil_artifact?: {
        document_id: string;
        page_id: string;
        page_name: string;
        output_file: string;
        root_node_id: string;
        created_nodes: number;
        share_url?: string;
    };
    layout_review?: {
        status: "valid" | "invalid";
        summary: string;
        findings: LayoutFinding[];
    };
}

export interface UiSpecification {
    schema_version: "2.0";
    screen_name: string;
    platform: "mobile" | "tablet" | "desktop" | "responsive";
    viewport_width: number;
    viewport_height: number;
    summary: string;
    root: UiNode;
}

export interface Run {
    id: string;
    session_id: string;
    revision: number;
    prompt: string;
    screen_name: string;
    platform: string;
    stage: RunStage;
    status: string;
    intent?: "chat" | "design";
    assistant_message?: string;
    library_ids: string[];
    mcp_profile?: OpenPencilProfile;
    specification?: UiSpecification;
    error?: {
        code: string;
        detail: string;
        retryable?: boolean;
        action?: string;
        stage?: RunStage;
    };
    created_at: string;
    updated_at: string;
}

export interface WorkflowEvent {
    id: string;
    run_id: string;
    revision: number;
    sequence: number;
    type: string;
    time: string;
    payload: Record<string, unknown>;
}

export interface ConnectionSettings {
    mcpEndpoint: string;
    sourceFile: string;
    knowledgeId: "auto" | "shadcn-ui" | "taptap";
}

export interface OpenPencilProfile {
    endpoint: string;
    source_file: string;
    output_file?: string;
    target_mode: "new_file";
    knowledge_id: ConnectionSettings["knowledgeId"];
}

export interface DesignSystemInfo {
    id: string;
    name: string;
    path: string;
    knowledge_id: "auto" | "shadcn-ui" | "taptap";
}

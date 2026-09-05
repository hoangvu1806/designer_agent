import { Braces, Check, Copy, Eye, MessageSquareText, X } from "lucide-react";
import { useEffect, useState } from "react";
import {
    PreviewCanvas,
    PreviewToolbar,
    type PreviewSize,
} from "./SemanticPreview";
import type { Run, RunArtifacts } from "./types";

interface Props {
    run?: Run;
    artifacts?: RunArtifacts;
    onReview: (
        decision: "approved" | "changes_requested",
        feedback?: string,
    ) => void;
}

export function ReviewPanel({ run, artifacts, onReview }: Props) {
    const [tab, setTab] = useState<"review" | "preview" | "json">("review");
    const [feedback, setFeedback] = useState("");
    const [previewSize, setPreviewSize] = useState<PreviewSize>("fit");
    const [previewExpanded, setPreviewExpanded] = useState(false);
    const [copiedJson, setCopiedJson] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    const handleAction = async (
        decision: "approved" | "changes_requested",
        fb?: string,
    ) => {
        if (submitting) return;
        setSubmitting(true);
        try {
            await onReview(decision, fb);
        } finally {
            setSubmitting(false);
        }
    };

    const canReview =
        (run?.stage === "review_spec" || run?.stage === "review_final") &&
        run.status === "waiting_review";
    const layout = artifacts?.layout_review;
    const finalBlocked =
        run?.stage === "review_final" && layout?.status !== "valid";

    const copyJson = async () => {
        if (!run?.specification) return;
        try {
            await navigator.clipboard.writeText(
                JSON.stringify(run.specification, null, 2),
            );
            setCopiedJson(true);
            setTimeout(() => setCopiedJson(false), 2000);
        } catch {
            // ignore
        }
    };

    useEffect(() => {
        if (!previewExpanded) return;
        const close = (event: KeyboardEvent) => {
            if (event.key === "Escape") setPreviewExpanded(false);
        };
        window.addEventListener("keydown", close);
        return () => window.removeEventListener("keydown", close);
    }, [previewExpanded]);

    return (
        <>
            <aside
                className="review-panel"
                aria-label="UI Specification Review Panel"
            >
                <header>
                    <div>
                        <span className="eyebrow">Workbench</span>
                        <h2>{run?.screen_name ?? "Review"}</h2>
                    </div>
                    <span
                        className="revision"
                        title={`Revision ${run?.revision ?? 1}`}
                    >
                        R{String(run?.revision ?? 1).padStart(2, "0")}
                    </span>
                </header>

                <div className="review-tabs">
                    <button
                        className={tab === "review" ? "active" : ""}
                        onClick={() => setTab("review")}
                        type="button"
                    >
                        <MessageSquareText size={15} /> Review
                    </button>
                    <button
                        className={tab === "preview" ? "active" : ""}
                        onClick={() => setTab("preview")}
                        type="button"
                    >
                        <Eye size={15} /> Preview
                    </button>
                    <button
                        className={tab === "json" ? "active" : ""}
                        onClick={() => setTab("json")}
                        type="button"
                    >
                        <Braces size={15} /> JSON
                    </button>
                </div>

                <div className="review-content">
                    {tab === "review" && (
                        <div className="review-copy">
                            <span className="review-kicker">
                                {canReview
                                    ? "Decision Required"
                                    : "Live Run Context"}
                            </span>
                            <h3>
                                {run?.intent === "chat"
                                    ? run.assistant_message
                                    : (run?.specification?.summary ??
                                      "The structured UI specification will appear here once ready.")}
                            </h3>

                            {run?.specification && (
                                <dl className="review-spec-meta">
                                    <div>
                                        <dt>Platform</dt>
                                        <dd>{run.specification.platform}</dd>
                                    </div>
                                    <div>
                                        <dt>Target Viewport</dt>
                                        <dd>
                                            {run.specification.viewport_width} ×{" "}
                                            {run.specification.viewport_height}{" "}
                                            px
                                        </dd>
                                    </div>
                                    <div>
                                        <dt>Current Stage</dt>
                                        <dd>
                                            {run.stage.replaceAll("_", " ")}
                                        </dd>
                                    </div>
                                    {run.mcp_profile?.output_file && (
                                        <div>
                                            <dt>Output File</dt>
                                            <dd
                                                title={
                                                    run.mcp_profile.output_file
                                                }
                                            >
                                                {run.mcp_profile.output_file}
                                            </dd>
                                        </div>
                                    )}
                                </dl>
                            )}

                            {artifacts?.knowledge_snapshot?.libraries
                                ?.length ? (
                                <p className="artifact-note">
                                    Knowledge:{" "}
                                    {artifacts.knowledge_snapshot.libraries.join(
                                        ", ",
                                    )}
                                </p>
                            ) : null}

                            {artifacts?.openpencil_artifact && (
                                <div className="artifact-card">
                                    <span>OpenPencil output</span>
                                    <strong>
                                        {
                                            artifacts.openpencil_artifact
                                                .page_name
                                        }
                                    </strong>
                                    <code>
                                        {
                                            artifacts.openpencil_artifact
                                                .output_file
                                        }
                                    </code>
                                    <button
                                        className="secondary-button compact"
                                        type="button"
                                        onClick={() =>
                                            navigator.clipboard.writeText(
                                                artifacts.openpencil_artifact
                                                    ?.output_file ?? "",
                                            )
                                        }
                                    >
                                        <Copy size={13} /> Copy path
                                    </button>
                                </div>
                            )}

                            {layout && (
                                <div
                                    className={`layout-result ${layout.status}`}
                                >
                                    <strong>Layout {layout.status}</strong>
                                    <p>{layout.summary}</p>
                                    {layout.findings.map((finding, index) => (
                                        <div
                                            className={`layout-finding ${finding.severity}`}
                                            key={`${finding.category}-${index}`}
                                        >
                                            <span>{finding.category}</span>
                                            <p>{finding.evidence}</p>
                                            <small>{finding.correction}</small>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {canReview && (
                                <div>
                                    <label
                                        htmlFor="review-feedback-input"
                                        style={{
                                            fontSize: "12px",
                                            fontWeight: 600,
                                            color: "var(--text-muted)",
                                            display: "block",
                                            marginBottom: "6px",
                                        }}
                                    >
                                        Revision Notes (Optional):
                                    </label>
                                    <textarea
                                        id="review-feedback-input"
                                        value={feedback}
                                        onChange={(event) =>
                                            setFeedback(event.target.value)
                                        }
                                        placeholder="Enter any feedback, design changes or adjustments needed..."
                                        rows={4}
                                    />
                                </div>
                            )}
                        </div>
                    )}

                    {tab === "preview" && (
                        <div className="preview-workbench">
                            <PreviewToolbar
                                size={previewSize}
                                expanded={false}
                                onSize={setPreviewSize}
                                onExpand={() => setPreviewExpanded(true)}
                            />
                            <PreviewCanvas run={run} size={previewSize} />
                        </div>
                    )}

                    {tab === "json" && (
                        <div className="json-view-container">
                            {run?.specification && (
                                <div className="json-view-header">
                                    <button
                                        className="md-copy-btn"
                                        onClick={copyJson}
                                        type="button"
                                        title="Copy specification JSON"
                                    >
                                        {copiedJson ? (
                                            <Check size={13} />
                                        ) : (
                                            <Copy size={13} />
                                        )}
                                        <span>
                                            {copiedJson
                                                ? "Copied"
                                                : "Copy JSON"}
                                        </span>
                                    </button>
                                </div>
                            )}
                            <pre>
                                {run?.specification
                                    ? JSON.stringify(
                                          {
                                              specification: run.specification,
                                              artifacts,
                                          },
                                          null,
                                          2,
                                      )
                                    : "No specification generated yet."}
                            </pre>
                        </div>
                    )}
                </div>

                {canReview && (
                    <footer>
                        <button
                            className="request-change"
                            onClick={() =>
                                handleAction("changes_requested", feedback)
                            }
                            disabled={submitting}
                            type="button"
                        >
                            <X size={16} /> Request Changes
                        </button>
                        <button
                            className="approve"
                            onClick={() => handleAction("approved")}
                            disabled={finalBlocked || submitting}
                            title={
                                finalBlocked
                                    ? "Resolve blocking layout findings first"
                                    : undefined
                            }
                            type="button"
                        >
                            <Check size={16} />{" "}
                            {submitting
                                ? "Processing..."
                                : run?.stage === "review_final"
                                  ? "Approve Design"
                                  : "Approve Structure"}
                        </button>
                    </footer>
                )}
            </aside>

            {previewExpanded && (
                <div
                    className="preview-modal"
                    role="dialog"
                    aria-modal="true"
                    aria-label={`${run?.screen_name ?? "UI"} Expanded Preview`}
                >
                    <header>
                        <div>
                            <span className="eyebrow">Responsive Preview</span>
                            <h2>{run?.screen_name ?? "Preview"}</h2>
                        </div>
                        <PreviewToolbar
                            size={previewSize}
                            expanded
                            onSize={setPreviewSize}
                            onExpand={() => setPreviewExpanded(false)}
                        />
                    </header>
                    <PreviewCanvas run={run} size={previewSize} />
                </div>
            )}
        </>
    );
}

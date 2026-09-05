import { ArrowUp, Bot, Layers, Library, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { PlatformSelector, STARTER_PROMPTS } from "./ChatControls";
import { MarkdownRenderer } from "./MarkdownRenderer";
import type { ConnectionSettings, Run, WorkflowEvent } from "./types";

interface Props {
    run?: Run;
    runs: Run[];
    events: WorkflowEvent[];
    busy: boolean;
    settings: ConnectionSettings;
    onSubmit: (value: {
        prompt: string;
        screenName: string;
        platform: string;
        libraryIds: string[];
    }) => void;
    onRetry: () => void;
    onCancel: () => void;
}

function eventText(event: WorkflowEvent) {
    const value = event.payload.message ?? event.payload.detail ?? event.type;
    return String(value).replaceAll("_", " ");
}

function getStageStatusText(stage?: string) {
    switch (stage) {
        case "requirement":
            return "Analyzing requirements & design intent...";
        case "specification":
            return "Structuring UI hierarchy & component layout...";
        case "review_spec":
            return "Preparing specification for review...";
        case "components":
            return "Searching design system library for components...";
        case "binding":
            return "Mapping components to design slots...";
        case "assembly":
            return "Rendering UI canvas in OpenPencil...";
        case "layout_check":
            return "Auditing layout spacing, hierarchy & contrast...";
        case "review_final":
            return "Finalizing design artifact...";
        default:
            return "Designer is thinking & preparing response...";
    }
}

function getStageBadge(stage?: string) {
    switch (stage) {
        case "requirement":
            return "Requirements";
        case "specification":
            return "Specification";
        case "components":
            return "Components";
        case "binding":
            return "Binding";
        case "assembly":
            return "Assembly";
        case "layout_check":
            return "Layout QA";
        case "review_spec":
        case "review_final":
            return "Review";
        default:
            return "Working";
    }
}

const HIDDEN_CONVERSATION_EVENTS = new Set(["run.created", "stage.changed"]);

export function ChatWorkspace({
    run,
    runs,
    events,
    busy,
    settings,
    onSubmit,
    onRetry,
    onCancel,
}: Props) {
    const [prompt, setPrompt] = useState("");
    const [screenName, setScreenName] = useState("");
    const [platform, setPlatform] = useState("responsive");
    const conversationEndRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const isAgentWorking =
        busy ||
        (run ? ["running", "queued", "starting"].includes(run.status) : false);

    const history = runs
        .filter((item) => item.id !== run?.id)
        .slice()
        .reverse();
    const visibleEvents =
        run?.intent === "chat"
            ? events.filter((event) => event.type === "assistant.message")
            : events.filter(
                  (event) => !HIDDEN_CONVERSATION_EVENTS.has(event.type),
              );

    const scrollToBottom = () => {
        conversationEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [run, runs, events, isAgentWorking]);

    const submit = () => {
        if (prompt.trim().length < 3 || !screenName.trim() || busy) return;
        onSubmit({
            prompt: prompt.trim(),
            screenName: screenName.trim(),
            platform,
            libraryIds:
                settings.knowledgeId === "auto" ? [] : [settings.knowledgeId],
        });
        setPrompt("");
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
        }
    };

    const selectStarter = (starter: (typeof STARTER_PROMPTS)[number]) => {
        setPrompt(starter.prompt);
        setScreenName(starter.screenName);
        setPlatform(starter.platform);
        if (textareaRef.current) {
            textareaRef.current.focus();
        }
    };

    return (
        <main className="chat-workspace" role="main">
            <section className="conversation" aria-live="polite">
                {!run && history.length === 0 && (
                    <div className="empty-conversation">
                        <span className="empty-orbit">
                            <Sparkles size={26} />
                        </span>
                        <h2>What would you like to build?</h2>
                        <p>
                            Describe your target screen, audience, and key
                            actions. The AI designer will turn your requirements
                            into structured, reviewable UI components.
                        </p>
                        <div className="starter-grid">
                            {STARTER_PROMPTS.map((starter) => (
                                <button
                                    key={starter.title}
                                    type="button"
                                    className="starter-card"
                                    onClick={() => selectStarter(starter)}
                                >
                                    <strong>{starter.title}</strong>
                                    <span>{starter.prompt}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {history.map((item) => (
                    <div className="turn-history" key={item.id}>
                        <article className="message user-message">
                            <small>You</small>
                            <p>{item.prompt}</p>
                        </article>
                        {item.assistant_message && (
                            <article className="message assistant-message">
                                <span className="assistant-avatar">
                                    <Bot size={17} />
                                </span>
                                <div className="assistant-body">
                                    <div className="assistant-header">
                                        <small>Designer</small>
                                    </div>
                                    <MarkdownRenderer
                                        content={item.assistant_message}
                                    />
                                </div>
                            </article>
                        )}
                    </div>
                ))}

                {run && (
                    <article className="message user-message">
                        <small>You</small>
                        <p>{run.prompt}</p>
                    </article>
                )}

                {visibleEvents.map((event) =>
                    event.type === "assistant.message" ? (
                        <article
                            className="message assistant-message"
                            key={event.id}
                        >
                            <span className="assistant-avatar">
                                <Bot size={17} />
                            </span>
                            <div className="assistant-body">
                                <div className="assistant-header">
                                    <small>Designer</small>
                                </div>
                                <MarkdownRenderer content={eventText(event)} />
                            </div>
                        </article>
                    ) : (
                        <article
                            className={`message event-message event-${event.type.replace(".", "-")}`}
                            key={event.id}
                        >
                            <span className="event-marker" />
                            <div>
                                <small>
                                    {event.type.replaceAll(".", " · ")}
                                </small>
                                <p>{eventText(event)}</p>
                            </div>
                        </article>
                    ),
                )}

                {run?.intent === "chat" &&
                    run.assistant_message &&
                    !visibleEvents.some(
                        (event) => event.type === "assistant.message",
                    ) && (
                        <article className="message assistant-message">
                            <span className="assistant-avatar">
                                <Bot size={17} />
                            </span>
                            <div className="assistant-body">
                                <div className="assistant-header">
                                    <small>Designer</small>
                                </div>
                                <MarkdownRenderer
                                    content={run.assistant_message}
                                />
                            </div>
                        </article>
                    )}

                {run?.error && (
                    <article className="message error-message">
                        <small>{run.error.code}</small>
                        <p>{run.error.detail}</p>
                        {run.error.action && <em>{run.error.action}</em>}
                        {(run.status === "failed" ||
                            run.status === "blocked") && (
                            <button
                                className="secondary-button compact"
                                onClick={onRetry}
                                type="button"
                            >
                                Retry this stage
                            </button>
                        )}
                    </article>
                )}

                {isAgentWorking && (
                    <article
                        className="message assistant-message typing-indicator-message"
                        aria-label="Designer is thinking"
                    >
                        <span className="assistant-avatar pulse-glow">
                            <Bot size={17} />
                        </span>
                        <div className="assistant-body">
                            <div className="assistant-header">
                                <small>Designer</small>
                                <span className="typing-header-stage">
                                    {getStageBadge(run?.stage)}
                                </span>
                            </div>
                            <div className="typing-bubble">
                                <div className="typing-dots" aria-hidden="true">
                                    <span className="typing-dot" />
                                    <span className="typing-dot" />
                                    <span className="typing-dot" />
                                </div>
                                <span className="typing-status-text">
                                    {getStageStatusText(run?.stage)}
                                </span>
                            </div>
                        </div>
                    </article>
                )}

                <div ref={conversationEndRef} />
            </section>

            <div className="composer-wrapper">
                <section
                    className="composer"
                    aria-label="Create design request"
                >
                    <div className="composer-input-area">
                        <textarea
                            ref={textareaRef}
                            value={prompt}
                            onChange={(event) => {
                                setPrompt(event.target.value);
                                if (textareaRef.current) {
                                    textareaRef.current.style.height = "auto";
                                    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
                                }
                            }}
                            onKeyDown={(event) => {
                                if (event.key === "Enter" && !event.shiftKey) {
                                    event.preventDefault();
                                    submit();
                                }
                            }}
                            placeholder="Ask anything, or describe a screen to generate..."
                            rows={1}
                        />
                    </div>

                    <div className="composer-bottom-bar">
                        <div className="composer-pills-left">
                            <div className="composer-mini-pill screen-pill">
                                <Layers
                                    size={13}
                                    style={{ color: "var(--violet)" }}
                                />
                                <span className="pill-label">Screen:</span>
                                <input
                                    value={screenName}
                                    onChange={(event) =>
                                        setScreenName(event.target.value)
                                    }
                                    placeholder="Output file name"
                                    title="Used as the .fig output file name"
                                />
                            </div>

                            <PlatformSelector
                                value={platform}
                                onChange={setPlatform}
                            />

                            {settings.sourceFile && (
                                <div
                                    className="composer-source-tag"
                                    title={`Component Source: ${settings.sourceFile}`}
                                >
                                    <Library size={12} />
                                    <span>
                                        {settings.sourceFile
                                            .split(/[\\/]/)
                                            .pop()}
                                    </span>
                                </div>
                            )}
                        </div>

                        <div className="composer-actions-right">
                            {busy && (
                                <button
                                    className="composer-cancel"
                                    onClick={onCancel}
                                    type="button"
                                >
                                    Cancel
                                </button>
                            )}
                            <span className="composer-shortcut">↵ Enter</span>
                            <button
                                className="composer-send-btn"
                                onClick={submit}
                                disabled={
                                    busy ||
                                    prompt.trim().length < 3 ||
                                    !screenName.trim()
                                }
                                title={
                                    busy
                                        ? "Agent is working..."
                                        : !screenName.trim()
                                          ? "Name the output file in the Screen field"
                                          : "Send prompt (Enter)"
                                }
                                type="button"
                            >
                                <ArrowUp size={16} strokeWidth={2.5} />
                            </button>
                        </div>
                    </div>
                </section>
            </div>
        </main>
    );
}

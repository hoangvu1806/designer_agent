import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { BuildRail } from "./BuildRail";
import { ChatWorkspace } from "./ChatWorkspace";
import {
    mcpProfile,
    normalizeMcpEndpoint,
    readSettings,
    requireMcpProfile,
} from "./connection";
import { openRunStream } from "./events";
import { ReviewPanel } from "./ReviewPanel";
import { SessionRail } from "./SessionRail";
import { SettingsDrawer } from "./SettingsDrawer";
import { useTheme } from "./theme";
import type { Run, RunArtifacts, Session, WorkflowEvent } from "./types";
import { WorkspaceHeader } from "./WorkspaceHeader";
import { sessionWorkflowState } from "./workflowState";

const MCP_RETRY_STAGES = new Set([
    "components",
    "binding",
    "assembly",
    "layout_check",
]);

export default function App() {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [activeSession, setActiveSession] = useState<Session>();
    const [runs, setRuns] = useState<Run[]>([]);
    const [activeRun, setActiveRun] = useState<Run>();
    const [events, setEvents] = useState<WorkflowEvent[]>([]);
    const [artifacts, setArtifacts] = useState<RunArtifacts>();
    const [collapsed, setCollapsed] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [reviewOpen, setReviewOpen] = useState(() => window.innerWidth > 900);
    const [connection, setConnection] = useState(readSettings);
    const [notice, setNotice] = useState("");
    const { resolvedTheme, toggleTheme } = useTheme();

    const applyRun = useCallback((updated: Run) => {
        setActiveRun((current) =>
            current?.id === updated.id ? updated : current,
        );
        setRuns((current) =>
            current.map((item) => (item.id === updated.id ? updated : item)),
        );
    }, []);

    useEffect(() => {
        api.listSessions()
            .then((items) => {
                setSessions(items);
                if (items[0]) setActiveSession(items[0]);
            })
            .catch((error) => setNotice(error.message));
    }, []);

    useEffect(() => {
        if (!activeSession) return;
        api.listRuns(activeSession.id)
            .then((items) => {
                setRuns(items);
                setActiveRun(items[0]);
                setEvents([]);
                setArtifacts(undefined);
            })
            .catch((error) => setNotice(error.message));
    }, [activeSession]);

    useEffect(() => {
        if (!activeRun) return;
        const source = openRunStream(activeRun.id, (event) => {
            setEvents((current) =>
                current.some((item) => item.id === event.id)
                    ? current
                    : [...current, event],
            );
            api.getRun(activeRun.id)
                .then(applyRun)
                .catch(() => undefined);
            api.getArtifacts(activeRun.id)
                .then(setArtifacts)
                .catch(() => undefined);
        });
        return () => source.close();
    }, [activeRun?.id, applyRun]);

    useEffect(() => {
        if (!activeRun) {
            setArtifacts(undefined);
            return;
        }
        api.getArtifacts(activeRun.id)
            .then(setArtifacts)
            .catch(() => undefined);
    }, [activeRun?.id, activeRun?.revision, activeRun?.stage]);

    useEffect(() => {
        if (!activeRun || !["queued", "running"].includes(activeRun.status))
            return;
        const timer = window.setInterval(() => {
            api.getRun(activeRun.id)
                .then(applyRun)
                .catch(() => undefined);
        }, 1500);
        return () => window.clearInterval(timer);
    }, [activeRun?.id, activeRun?.status, applyRun]);

    const busy = useMemo(
        () => activeRun?.status === "running" || activeRun?.status === "queued",
        [activeRun],
    );
    const workflow = useMemo(
        () => sessionWorkflowState(activeRun, runs, events),
        [activeRun, runs, events],
    );

    const createSession = async () => {
        try {
            const session = await api.createSession(
                `Design session ${sessions.length + 1}`,
            );
            setSessions((current) => [session, ...current]);
            setActiveSession(session);
            setActiveRun(undefined);
        } catch (error) {
            setNotice((error as Error).message);
        }
    };

    const submit = async (value: {
        prompt: string;
        screenName: string;
        platform: string;
        libraryIds: string[];
    }) => {
        try {
            let session = activeSession;
            if (!session) {
                session = await api.createSession(value.screenName);
                setSessions((current) => [session!, ...current]);
                setActiveSession(session);
            }
            const run = await api.createRun(session.id, {
                prompt: value.prompt,
                screen_name: value.screenName,
                platform: value.platform,
                library_ids: value.libraryIds,
                mcp_profile: mcpProfile(connection),
            });
            setRuns((current) => [run, ...current]);
            setActiveRun(run);
            setEvents([]);
            setArtifacts(undefined);
            setNotice("");
        } catch (error) {
            setNotice((error as Error).message);
        }
    };

    const review = async (
        decision: "approved" | "changes_requested",
        feedback = "",
    ) => {
        if (!activeRun) return;
        try {
            const checkpoint =
                activeRun.stage === "review_final" ? "final" : "specification";
            const currentProfile =
                decision === "approved" && checkpoint === "specification"
                    ? requireMcpProfile(connection)
                    : mcpProfile(connection);
            await api.review(
                activeRun.id,
                activeRun.revision,
                checkpoint,
                decision,
                feedback,
                currentProfile,
            );
            setActiveRun(await api.getRun(activeRun.id));
        } catch (error) {
            setNotice((error as Error).message);
        }
    };

    return (
        <div
            className={`app-shell ${collapsed ? "rail-collapsed" : ""} ${reviewOpen ? "" : "review-closed"}`}
        >
            <SessionRail
                sessions={sessions}
                activeId={activeSession?.id}
                collapsed={collapsed}
                onToggle={() => setCollapsed(!collapsed)}
                onSelect={setActiveSession}
                onCreate={createSession}
                onSettings={() => setSettingsOpen(true)}
            />

            <WorkspaceHeader
                session={activeSession}
                run={activeRun}
                theme={resolvedTheme}
                reviewOpen={reviewOpen}
                onTheme={toggleTheme}
                onReview={() => setReviewOpen(!reviewOpen)}
                onSettings={() => setSettingsOpen(true)}
            />

            <section className="timeline-slot">
                <BuildRail stage={workflow?.stage} status={workflow?.status} />
            </section>

            <ChatWorkspace
                run={activeRun}
                runs={runs}
                events={events}
                busy={busy}
                settings={connection}
                onSubmit={submit}
                onRetry={async () => {
                    if (!activeRun) return;
                    try {
                        const profile = MCP_RETRY_STAGES.has(
                            activeRun.error?.stage ?? "",
                        )
                            ? requireMcpProfile(connection)
                            : mcpProfile(connection);
                        await api.retry(activeRun.id, profile);
                        applyRun(await api.getRun(activeRun.id));
                    } catch (error) {
                        setNotice((error as Error).message);
                    }
                }}
                onCancel={async () => {
                    if (!activeRun) return;
                    try {
                        await api.cancel(activeRun.id);
                        applyRun(await api.getRun(activeRun.id));
                    } catch (error) {
                        setNotice((error as Error).message);
                    }
                }}
            />

            {reviewOpen && (
                <ReviewPanel
                    run={activeRun}
                    artifacts={artifacts}
                    onReview={review}
                />
            )}

            {notice && (
                <button
                    className="notice"
                    onClick={() => setNotice("")}
                    type="button"
                >
                    {notice} (Click to dismiss)
                </button>
            )}

            {settingsOpen && (
                <SettingsDrawer
                    value={connection}
                    onClose={() => setSettingsOpen(false)}
                    onSave={(value) => {
                        const normalized = {
                            ...value,
                            mcpEndpoint: normalizeMcpEndpoint(
                                value.mcpEndpoint,
                            ),
                            sourceFile: value.sourceFile.trim(),
                        };
                        setConnection(normalized);
                        localStorage.setItem(
                            "designer.connection",
                            JSON.stringify(normalized),
                        );
                        setSettingsOpen(false);
                    }}
                    onProbe={async (endpoint) => {
                        const result = await api.probeMcp(
                            normalizeMcpEndpoint(endpoint),
                        );
                        if (!result.reachable) throw new Error(result.message);
                        return result.message;
                    }}
                    onLoadComponents={(value) =>
                        api.listComponents(requireMcpProfile(value))
                    }
                />
            )}
        </div>
    );
}

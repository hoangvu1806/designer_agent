import {
    CheckCircle2,
    Laptop,
    Moon,
    PlugZap,
    RefreshCw,
    Sun,
    X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "./api";
import { useTheme } from "./theme";
import type { ConnectionSettings, DesignSystemInfo } from "./types";

interface Props {
    value: ConnectionSettings;
    onClose: () => void;
    onSave: (value: ConnectionSettings) => void;
    onProbe: (endpoint: string) => Promise<string>;
    onLoadComponents: (
        value: ConnectionSettings,
    ) => Promise<
        { component_id: string; name: string; canonical_path: string }[]
    >;
}

export function SettingsDrawer({
    value,
    onClose,
    onSave,
    onProbe,
    onLoadComponents,
}: Props) {
    const [draft, setDraft] = useState(value);
    const [designSystems, setDesignSystems] = useState<DesignSystemInfo[]>([]);
    const [result, setResult] = useState<{ message: string; ok: boolean }>();
    const [probing, setProbing] = useState(false);
    const [busy, setBusy] = useState(false);
    const { theme, setTheme } = useTheme();

    useEffect(() => {
        api.listDesignSystems()
            .then(setDesignSystems)
            .catch(() => undefined);
    }, []);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [onClose]);

    const handleProbe = async () => {
        if (!draft.mcpEndpoint.trim()) {
            setResult({ message: "Enter the MCP endpoint first.", ok: false });
            return;
        }
        setProbing(true);
        try {
            const msg = await onProbe(draft.mcpEndpoint);
            setResult({ message: msg, ok: true });
        } catch (err) {
            setResult({ message: (err as Error).message, ok: false });
        } finally {
            setProbing(false);
        }
    };

    const sync = async () => {
        setBusy(true);
        try {
            const items = await onLoadComponents(draft);
            setResult({
                message: `Synced ${items.length} components.`,
                ok: true,
            });
        } catch (error) {
            setResult({ message: (error as Error).message, ok: false });
        } finally {
            setBusy(false);
        }
    };

    return (
        <div
            className="drawer-backdrop"
            role="presentation"
            onMouseDown={onClose}
        >
            <aside
                className="settings-drawer"
                role="dialog"
                aria-modal="true"
                aria-label="Agentic Designer Settings"
                onMouseDown={(event) => event.stopPropagation()}
            >
                <header>
                    <div>
                        <span className="eyebrow">Control Plane</span>
                        <h2>Workspace Settings</h2>
                    </div>
                    <button
                        className="icon-button"
                        onClick={onClose}
                        title="Close settings"
                        type="button"
                    >
                        <X size={18} />
                    </button>
                </header>

                <p className="drawer-intro">
                    Configure visual appearance, OpenPencil MCP endpoints, and
                    component library sources.
                </p>

                {/* Section: Appearance & Theme */}
                <section>
                    <h3>Appearance & Theme</h3>
                    <div className="theme-options-grid">
                        <button
                            type="button"
                            className={`theme-option-btn ${theme === "light" ? "active" : ""}`}
                            onClick={() => setTheme("light")}
                            title="Light theme"
                        >
                            <Sun size={20} />
                            <span>Light</span>
                        </button>
                        <button
                            type="button"
                            className={`theme-option-btn ${theme === "dark" ? "active" : ""}`}
                            onClick={() => setTheme("dark")}
                            title="Dark theme"
                        >
                            <Moon size={20} />
                            <span>Dark</span>
                        </button>
                        <button
                            type="button"
                            className={`theme-option-btn ${theme === "system" ? "active" : ""}`}
                            onClick={() => setTheme("system")}
                            title="Sync with system preference"
                        >
                            <Laptop size={20} />
                            <span>System</span>
                        </button>
                    </div>
                </section>

                {/* Section: MCP Runtime */}
                <section>
                    <h3>OpenPencil MCP Runtime</h3>
                    <label>
                        MCP Server Endpoint
                        <input
                            value={draft.mcpEndpoint}
                            onChange={(event) =>
                                setDraft({
                                    ...draft,
                                    mcpEndpoint: event.target.value,
                                })
                            }
                            placeholder="MCP endpoint"
                        />
                    </label>
                    <div className="probe-row">
                        <button
                            className="secondary-button"
                            onClick={handleProbe}
                            disabled={probing}
                            type="button"
                        >
                            <PlugZap size={15} />
                            <span>
                                {probing ? "Testing..." : "Test Connection"}
                            </span>
                        </button>
                        {result && (
                            <span className={result.ok ? "success" : "error"}>
                                {result.ok ? (
                                    <CheckCircle2 size={15} />
                                ) : (
                                    <X size={15} />
                                )}
                                {result.message}
                            </span>
                        )}
                    </div>
                </section>

                {/* Section: Files */}
                <section>
                    <h3>Design System & Files</h3>
                    {designSystems.length > 0 && (
                        <label>
                            Installed Design Systems
                            <select
                                value={
                                    designSystems.find(
                                        (s) => s.path === draft.sourceFile,
                                    )?.id ?? ""
                                }
                                onChange={(event) => {
                                    const selected = designSystems.find(
                                        (s) => s.id === event.target.value,
                                    );
                                    if (selected) {
                                        setDraft({
                                            ...draft,
                                            sourceFile: selected.path,
                                            knowledgeId: selected.knowledge_id,
                                        });
                                    }
                                }}
                            >
                                <option value="">
                                    -- Select an installed design system --
                                </option>
                                {designSystems.map((ds) => (
                                    <option key={ds.id} value={ds.id}>
                                        {ds.name}
                                    </option>
                                ))}
                            </select>
                        </label>
                    )}
                    <label>
                        Component Knowledge
                        <select
                            value={draft.knowledgeId}
                            onChange={(event) =>
                                setDraft({
                                    ...draft,
                                    knowledgeId: event.target
                                        .value as ConnectionSettings["knowledgeId"],
                                })
                            }
                        >
                            <option value="auto">
                                Auto detect from source file
                            </option>
                            <option value="shadcn-ui">shadcn/ui catalog</option>
                            <option value="taptap">TapTap catalog</option>
                        </select>
                    </label>
                    <label>
                        Component Source (.fig)
                        <input
                            value={draft.sourceFile}
                            onChange={(event) =>
                                setDraft({
                                    ...draft,
                                    sourceFile: event.target.value,
                                })
                            }
                            placeholder="Full path or installed system name"
                        />
                    </label>
                    <p className="field-note">
                        The source `.fig` is read directly from disk and is
                        never opened through MCP. OpenPencil MCP is used only to
                        write a per-run output file named from the Screen field.
                    </p>
                </section>

                {/* Section: Component Catalog */}
                <section>
                    <div
                        className="section-heading"
                        style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "12px",
                        }}
                    >
                        <h3 style={{ margin: 0 }}>Component Catalog</h3>
                        <button
                            className="secondary-button compact"
                            onClick={sync}
                            disabled={busy}
                            type="button"
                        >
                            <RefreshCw
                                size={13}
                                className={busy ? "spin" : ""}
                            />
                            <span>{busy ? "Syncing..." : "Sync Catalog"}</span>
                        </button>
                    </div>
                </section>

                <footer>
                    <button
                        className="secondary-button"
                        onClick={onClose}
                        type="button"
                    >
                        Cancel
                    </button>
                    <button
                        className="primary-button"
                        onClick={() => onSave(draft)}
                        type="button"
                    >
                        Save Settings
                    </button>
                </footer>
            </aside>
        </div>
    );
}

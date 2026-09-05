import { ChevronLeft, ChevronRight, LayoutGrid, Plus, Settings2, Sparkles } from "lucide-react";
import type { Session } from "./types";

interface Props {
  sessions: Session[];
  activeId?: string;
  collapsed: boolean;
  onToggle: () => void;
  onSelect: (session: Session) => void;
  onCreate: () => void;
  onSettings: () => void;
}

export function SessionRail(props: Props) {
  return (
    <aside
      className={`session-rail ${props.collapsed ? "is-collapsed" : ""}`}
      aria-label="Workspace sidebar"
    >
      <div className="brand-lockup">
        <span className="brand-mark" title="OpenPencil Agentic Designer">
          <Sparkles size={18} />
        </span>
        {!props.collapsed && (
          <div>
            <strong>Designer Studio</strong>
            <small>AI-Powered UI Agent</small>
          </div>
        )}
      </div>

      <button
        className="new-session"
        onClick={props.onCreate}
        title="Create new design session"
      >
        <Plus size={18} strokeWidth={2.2} />
        {!props.collapsed && <span>New Session</span>}
      </button>

      {!props.collapsed && (
        <div className="rail-label">
          <span>Recent Sessions ({props.sessions.length})</span>
        </div>
      )}

      <nav className="session-list" aria-label="Design sessions">
        {props.sessions.map((session) => (
          <button
            key={session.id}
            className={session.id === props.activeId ? "active" : ""}
            onClick={() => props.onSelect(session)}
            title={session.title}
          >
            <span className="session-dot" />
            {!props.collapsed ? (
              <span>{session.title}</span>
            ) : (
              <LayoutGrid size={16} />
            )}
          </button>
        ))}
        {props.sessions.length === 0 && !props.collapsed && (
          <div style={{ padding: "12px", color: "var(--text-muted)", fontSize: "12.5px" }}>
            No sessions yet. Click New Session to start.
          </div>
        )}
      </nav>

      <div className="rail-footer">
        <button
          onClick={props.onSettings}
          title="Open MCP & Connection Settings"
        >
          <Settings2 size={18} />
          {!props.collapsed && <span>Settings & MCP</span>}
        </button>
        <button
          onClick={props.onToggle}
          title={props.collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {props.collapsed ? (
            <ChevronRight size={18} />
          ) : (
            <>
              <ChevronLeft size={18} />
              <span>Collapse Sidebar</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}

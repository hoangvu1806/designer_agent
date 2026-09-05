import type { OpenPencilProfile, Run, RunArtifacts, Session } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL;

if (!API_BASE) throw new Error("VITE_API_BASE_URL is required");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: { "Content-Type": "application/json", ...init?.headers },
    });
    if (!response.ok) {
        const problem = (await response
            .json()
            .catch(() => ({ detail: response.statusText }))) as {
            detail?: string | { loc?: (string | number)[]; msg?: string }[];
        };
        const message = Array.isArray(problem.detail)
            ? problem.detail
                  .map(
                      (item) =>
                          `${item.loc?.slice(1).join(".") || "request"}: ${item.msg || "invalid value"}`,
                  )
                  .join("; ")
            : problem.detail || "Request failed";
        throw new Error(message);
    }
    return response.json() as Promise<T>;
}

export const api = {
    listSessions: () => request<Session[]>("/sessions"),
    createSession: (title: string) =>
        request<Session>("/sessions", {
            method: "POST",
            body: JSON.stringify({ title }),
        }),
    listRuns: (sessionId: string) =>
        request<Run[]>(`/sessions/${sessionId}/runs`),
    getRun: (runId: string) => request<Run>(`/runs/${runId}`),
    getArtifacts: (runId: string) =>
        request<RunArtifacts>(`/runs/${runId}/artifacts`),
    createRun: (
        sessionId: string,
        body: {
            prompt: string;
            screen_name: string;
            platform: string;
            library_ids: string[];
            mcp_profile?: OpenPencilProfile;
        },
    ) =>
        request<Run>(`/sessions/${sessionId}/runs`, {
            method: "POST",
            body: JSON.stringify(body),
        }),
    review: (
        runId: string,
        revision: number,
        checkpoint: "specification" | "final",
        decision: string,
        feedback = "",
        mcpProfile?: OpenPencilProfile,
    ) =>
        request<{ status: string }>(`/runs/${runId}/reviews`, {
            method: "POST",
            body: JSON.stringify({
                checkpoint,
                decision,
                revision,
                feedback,
                mcp_profile: mcpProfile,
            }),
        }),
    retry: (runId: string, mcpProfile?: OpenPencilProfile) =>
        request<{ status: string }>(`/runs/${runId}/retry`, {
            method: "POST",
            body: JSON.stringify({ mcp_profile: mcpProfile }),
        }),
    cancel: (runId: string) =>
        request<{ status: string }>(`/runs/${runId}/cancel`, {
            method: "POST",
        }),
    probeMcp: (endpoint: string) =>
        request<{ reachable: boolean; message: string }>(
            "/integrations/openpencil/probe",
            {
                method: "POST",
                body: JSON.stringify({ endpoint }),
            },
        ),
    listComponents: (profile: OpenPencilProfile) =>
        request<
            { component_id: string; name: string; canonical_path: string }[]
        >("/integrations/openpencil/components", {
            method: "POST",
            body: JSON.stringify(profile),
        }),
    listDesignSystems: () =>
        request<import("./types").DesignSystemInfo[]>("/design-systems"),
    eventUrl: (runId: string) => `${API_BASE}/runs/${runId}/events`,
};

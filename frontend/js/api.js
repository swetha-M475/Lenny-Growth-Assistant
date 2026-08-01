/**
 * API Client — Handles communication with the FastAPI backend.
 * Supports REST calls and Server-Sent Events (SSE) for streaming chat.
 */

const API_BASE = window.location.origin + '/api';

const api = {
    // ─── Sessions ─────────────────────────────────────────

    async createSession(title = 'New Chat') {
        const res = await fetch(`${API_BASE}/sessions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title }),
        });
        if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
        return res.json();
    },

    async listSessions() {
        const res = await fetch(`${API_BASE}/sessions`);
        if (!res.ok) throw new Error(`Failed to list sessions: ${res.status}`);
        return res.json();
    },

    async getSession(sessionId) {
        const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
        if (!res.ok) throw new Error(`Failed to get session: ${res.status}`);
        return res.json();
    },

    async deleteSession(sessionId) {
        const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
            method: 'DELETE',
        });
        if (!res.ok) throw new Error(`Failed to delete session: ${res.status}`);
    },

    async updateSession(sessionId, title) {
        const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title }),
        });
        if (!res.ok) throw new Error(`Failed to update session: ${res.status}`);
        return res.json();
    },

    // ─── Chat (SSE Streaming) ────────────────────────────

    /**
     * Send a chat message and process the SSE stream.
     * @param {string} sessionId 
     * @param {string} content 
     * @param {string} skillHint - "auto", "qa", "ship30for30", "artifact"
     * @param {object} callbacks - { onSkill, onToken, onArtifact, onDone, onError }
     */
    async sendMessage(sessionId, content, skillHint, callbacks) {
        const res = await fetch(`${API_BASE}/chat/${sessionId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, skill_hint: skillHint }),
        });

        if (!res.ok) {
            const err = await res.text();
            throw new Error(`Chat request failed: ${res.status} - ${err}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith('event:')) {
                    const eventType = line.slice(6).trim();
                    continue; // Event type is on the next data line
                }
                if (line.startsWith('data:')) {
                    const rawData = line.slice(5).trim();
                    if (!rawData) continue;

                    try {
                        const data = JSON.parse(rawData);
                        // Determine event type from the data structure
                        if (data.skill) callbacks.onSkill?.(data.skill);
                        else if (data.token !== undefined) callbacks.onToken?.(data.token);
                        else if (data.id && data.type && data.content) callbacks.onArtifact?.(data);
                        else if (data.message_id) callbacks.onDone?.(data);
                        else if (data.error) callbacks.onError?.(data.error);
                    } catch (e) {
                        // Not JSON, skip
                    }
                }
            }
        }
    },

    // ─── Messages ────────────────────────────────────────

    async getMessages(sessionId) {
        const res = await fetch(`${API_BASE}/chat/${sessionId}/messages`);
        if (!res.ok) throw new Error(`Failed to get messages: ${res.status}`);
        return res.json();
    },

    // ─── Config ──────────────────────────────────────────

    async getConfig() {
        const res = await fetch(`${API_BASE}/config`);
        if (!res.ok) throw new Error(`Failed to get config: ${res.status}`);
        return res.json();
    },

    async updateConfig(provider, modelName, apiKey) {
        const res = await fetch(`${API_BASE}/config`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                llm_provider: provider,
                model_name: modelName || null,
                api_key: apiKey || null,
            }),
        });
        if (!res.ok) throw new Error(`Failed to update config: ${res.status}`);
        return res.json();
    },

    async healthCheck() {
        const res = await fetch(`${API_BASE}/config/health`);
        if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
        return res.json();
    },
};

// Make globally available
window.api = api;

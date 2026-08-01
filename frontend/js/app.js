/**
 * The Lenny Growth Assistant — Main Application Logic
 * 
 * Handles UI state, session management, chat flow, artifact rendering,
 * and settings management.
 */

// ─── State ─────────────────────────────────────────────────
const state = {
    sessions: [],
    activeSessionId: null,
    messages: [],
    artifacts: [],
    isStreaming: false,
    currentProvider: 'ollama',
};

// ─── DOM Elements ──────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const dom = {
    sidebar: $('sidebar'),
    sidebarToggle: $('sidebar-toggle'),
    newChatBtn: $('new-chat-btn'),
    sessionsList: $('sessions-list'),
    chatTitle: $('chat-title'),
    messagesContainer: $('messages-container'),
    welcomeScreen: $('welcome-screen'),
    chatInput: $('chat-input'),
    sendBtn: $('send-btn'),
    skillSelect: $('skill-select'),
    artifactPanel: $('artifact-panel'),
    artifactContent: $('artifact-content'),
    artifactTabs: $('artifact-tabs'),
    artifactToggleBtn: $('artifact-toggle-btn'),
    artifactCloseBtn: $('artifact-close-btn'),
    artifactCopyBtn: $('artifact-copy-btn'),
    settingsBtn: $('settings-btn'),
    settingsModal: $('settings-modal'),
    settingsCloseBtn: $('settings-close-btn'),
    modelInput: $('model-input'),
    apiKeyInput: $('api-key-input'),
    apiKeyGroup: $('api-key-group'),
    testConnectionBtn: $('test-connection-btn'),
    saveSettingsBtn: $('save-settings-btn'),
    connectionStatus: $('connection-status'),
    providerLabel: $('provider-label'),
    mobileMenuBtn: $('mobile-menu-btn'),
};

// ─── Initialize ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();
    await loadConfig();
    await loadSessions();

    // Configure marked.js for Markdown rendering
    if (window.marked) {
        marked.setOptions({
            highlight: function (code, lang) {
                if (window.hljs && lang && hljs.getLanguage(lang)) {
                    return hljs.highlight(code, { language: lang }).value;
                }
                return code;
            },
            breaks: true,
            gfm: true,
        });
    }
});

// ─── Event Listeners ───────────────────────────────────────
function setupEventListeners() {
    // Sidebar
    dom.sidebarToggle.addEventListener('click', toggleSidebar);
    dom.mobileMenuBtn.addEventListener('click', toggleSidebar);

    // New Chat
    dom.newChatBtn.addEventListener('click', createNewChat);

    // Chat Input
    dom.chatInput.addEventListener('input', handleInputChange);
    dom.chatInput.addEventListener('keydown', handleInputKeydown);
    dom.sendBtn.addEventListener('click', sendMessage);

    // Suggestion Chips
    document.querySelectorAll('.suggestion-chip').forEach((chip) => {
        chip.addEventListener('click', () => {
            dom.chatInput.value = chip.dataset.prompt;
            handleInputChange();
            sendMessage();
        });
    });

    // Artifact Panel
    dom.artifactCloseBtn.addEventListener('click', closeArtifactPanel);
    dom.artifactToggleBtn.addEventListener('click', toggleArtifactPanel);
    dom.artifactCopyBtn.addEventListener('click', copyArtifactContent);

    // Settings
    dom.settingsBtn.addEventListener('click', openSettings);
    dom.settingsCloseBtn.addEventListener('click', closeSettings);
    dom.settingsModal.addEventListener('click', (e) => {
        if (e.target === dom.settingsModal) closeSettings();
    });

    document.querySelectorAll('.provider-card').forEach((card) => {
        card.addEventListener('click', () => selectProvider(card.dataset.provider));
    });

    dom.testConnectionBtn.addEventListener('click', testConnection);
    dom.saveSettingsBtn.addEventListener('click', saveSettings);
}

// ─── Session Management ────────────────────────────────────
async function loadSessions() {
    try {
        state.sessions = await api.listSessions();
        renderSessionsList();
    } catch (e) {
        console.error('Failed to load sessions:', e);
    }
}

function renderSessionsList() {
    dom.sessionsList.innerHTML = '';
    state.sessions.forEach((session) => {
        const item = document.createElement('div');
        item.className = `session-item${session.id === state.activeSessionId ? ' active' : ''}`;
        item.innerHTML = `
            <span class="session-title">${escapeHtml(session.title)}</span>
            <button class="session-delete" title="Delete">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                </svg>
            </button>
        `;
        item.querySelector('.session-title').addEventListener('click', () => switchSession(session.id));
        item.querySelector('.session-delete').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteSession(session.id);
        });
        dom.sessionsList.appendChild(item);
    });
}

async function createNewChat() {
    try {
        const session = await api.createSession();
        state.sessions.unshift(session);
        state.activeSessionId = session.id;
        state.messages = [];
        state.artifacts = [];
        renderSessionsList();
        renderMessages();
        dom.chatTitle.textContent = session.title;
        showWelcomeScreen();
        dom.chatInput.focus();

        // Close sidebar on mobile
        if (window.innerWidth <= 768) {
            dom.sidebar.classList.add('collapsed');
        }
    } catch (e) {
        console.error('Failed to create session:', e);
        showToast('Failed to create new chat. Is the backend running?', 'error');
    }
}

async function switchSession(sessionId) {
    if (sessionId === state.activeSessionId || state.isStreaming) return;

    state.activeSessionId = sessionId;
    renderSessionsList();

    try {
        const session = await api.getSession(sessionId);
        state.messages = session.messages || [];
        state.artifacts = session.artifacts || [];
        dom.chatTitle.textContent = session.title;
        renderMessages();

        if (state.artifacts.length > 0) {
            dom.artifactToggleBtn.style.display = 'flex';
        } else {
            dom.artifactToggleBtn.style.display = 'none';
            closeArtifactPanel();
        }

        // Close sidebar on mobile
        if (window.innerWidth <= 768) {
            dom.sidebar.classList.add('collapsed');
        }
    } catch (e) {
        console.error('Failed to load session:', e);
    }
}

async function deleteSession(sessionId) {
    try {
        await api.deleteSession(sessionId);
        state.sessions = state.sessions.filter((s) => s.id !== sessionId);

        if (state.activeSessionId === sessionId) {
            state.activeSessionId = null;
            state.messages = [];
            state.artifacts = [];
            dom.chatTitle.textContent = 'New Chat';
            showWelcomeScreen();
            closeArtifactPanel();
        }

        renderSessionsList();
    } catch (e) {
        console.error('Failed to delete session:', e);
    }
}

// ─── Chat Flow ─────────────────────────────────────────────
function handleInputChange() {
    const value = dom.chatInput.value.trim();
    dom.sendBtn.disabled = !value || state.isStreaming;

    // Auto-resize textarea
    dom.chatInput.style.height = 'auto';
    dom.chatInput.style.height = Math.min(dom.chatInput.scrollHeight, 200) + 'px';
}

function handleInputKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!dom.sendBtn.disabled) sendMessage();
    }
}

async function sendMessage() {
    const content = dom.chatInput.value.trim();
    if (!content || state.isStreaming) return;

    // Ensure we have an active session
    if (!state.activeSessionId) {
        await createNewChat();
        if (!state.activeSessionId) return; // Exit if session creation failed
    }

    const skillHint = dom.skillSelect.value;

    // Add user message to UI
    const userMsg = {
        id: crypto.randomUUID(),
        role: 'user',
        content: content,
        created_at: new Date().toISOString(),
        artifacts: [],
    };
    state.messages.push(userMsg);
    hideWelcomeScreen();
    renderMessages();

    // Clear input
    dom.chatInput.value = '';
    dom.chatInput.style.height = 'auto';
    dom.sendBtn.disabled = true;
    state.isStreaming = true;

    // Add streaming placeholder for assistant
    const assistantMsg = {
        id: 'streaming',
        role: 'assistant',
        content: '',
        skill_used: null,
        created_at: new Date().toISOString(),
        artifacts: [],
    };
    state.messages.push(assistantMsg);
    renderMessages();
    scrollToBottom();

    try {
        await api.sendMessage(state.activeSessionId, content, skillHint, {
            onSkill(skill) {
                assistantMsg.skill_used = skill;
                updateStreamingMessage(assistantMsg);
            },
            onToken(token) {
                assistantMsg.content += token;
                updateStreamingMessage(assistantMsg);
                scrollToBottom();
            },
            onArtifact(artifact) {
                assistantMsg.artifacts.push(artifact);
                state.artifacts.push(artifact);
                dom.artifactToggleBtn.style.display = 'flex';
                showArtifact(artifact);
            },
            onDone(data) {
                assistantMsg.id = data.message_id;
                if (data.session_title) {
                    dom.chatTitle.textContent = data.session_title;
                    // Update session in list
                    const s = state.sessions.find((s) => s.id === state.activeSessionId);
                    if (s) {
                        s.title = data.session_title;
                        renderSessionsList();
                    }
                }
            },
            onError(error) {
                assistantMsg.content += `\n\n⚠️ Error: ${error}`;
                updateStreamingMessage(assistantMsg);
            },
        });
    } catch (e) {
        console.error('Chat error:', e);
        assistantMsg.content = `⚠️ Failed to get response. ${e.message}\n\nMake sure the backend is running and the LLM provider is configured.`;
        updateStreamingMessage(assistantMsg);
    }

    state.isStreaming = false;
    dom.sendBtn.disabled = !dom.chatInput.value.trim();

    // Remove streaming cursor
    const streamingEl = document.querySelector('.streaming-cursor');
    if (streamingEl) streamingEl.classList.remove('streaming-cursor');

    // Re-render final message with full markdown
    renderMessages();
    scrollToBottom();
}

// ─── Message Rendering ─────────────────────────────────────
function renderMessages() {
    if (state.messages.length === 0) {
        showWelcomeScreen();
        return;
    }

    hideWelcomeScreen();
    const container = dom.messagesContainer;

    // Keep welcome screen element but build messages after it
    const existing = container.querySelectorAll('.message');
    existing.forEach((el) => el.remove());

    state.messages.forEach((msg) => {
        const el = createMessageElement(msg);
        container.appendChild(el);
    });

    scrollToBottom();
}

function createMessageElement(msg) {
    const div = document.createElement('div');
    div.className = `message ${msg.role}`;
    div.dataset.id = msg.id;

    const avatarEmoji = msg.role === 'user' ? '👤' : '✨';
    const senderName = msg.role === 'user' ? 'You' : 'Lenny Assistant';

    // Build skill badge
    let skillBadge = '';
    if (msg.skill_used) {
        const labels = { qa: 'Q&A', ship30for30: 'Ship30', artifact: 'Artifact' };
        skillBadge = `<span class="skill-badge ${msg.skill_used}">${labels[msg.skill_used] || msg.skill_used}</span>`;
    }

    // Render content
    let renderedContent = '';
    if (msg.role === 'assistant') {
        // Strip artifact tags from displayed content
        let cleanContent = msg.content.replace(/<artifact[^>]*>[\s\S]*?<\/artifact>/g, '').trim();
        renderedContent = renderMarkdown(cleanContent);
    } else {
        renderedContent = escapeHtml(msg.content);
    }

    // Build artifact buttons
    let artifactBtns = '';
    if (msg.artifacts && msg.artifacts.length > 0) {
        msg.artifacts.forEach((a) => {
            artifactBtns += `
                <button class="view-artifact-btn" data-artifact-id="${a.id}" onclick="showArtifactById('${a.id}')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                        <path d="M12 3v18"/>
                    </svg>
                    ${escapeHtml(a.title || 'View Artifact')}
                </button>
            `;
        });
    }

    div.innerHTML = `
        <div class="message-avatar">${avatarEmoji}</div>
        <div class="message-body">
            <div class="message-meta">
                <span class="message-sender">${senderName}</span>
                ${skillBadge}
            </div>
            <div class="message-content${msg.id === 'streaming' ? ' streaming-cursor' : ''}">
                ${renderedContent}
            </div>
            ${artifactBtns}
        </div>
    `;

    return div;
}

function updateStreamingMessage(msg) {
    const el = document.querySelector('.message[data-id="streaming"]');
    if (!el) return;

    // Update skill badge
    if (msg.skill_used) {
        const metaEl = el.querySelector('.message-meta');
        const labels = { qa: 'Q&A', ship30for30: 'Ship30', artifact: 'Artifact' };
        if (!metaEl.querySelector('.skill-badge')) {
            metaEl.innerHTML += `<span class="skill-badge ${msg.skill_used}">${labels[msg.skill_used] || msg.skill_used}</span>`;
        }
    }

    // Update content — render as markdown incrementally
    const contentEl = el.querySelector('.message-content');
    let cleanContent = msg.content.replace(/<artifact[^>]*>[\s\S]*?<\/artifact>/g, '').trim();
    contentEl.innerHTML = renderMarkdown(cleanContent);
    contentEl.classList.add('streaming-cursor');
}

function renderMarkdown(text) {
    if (!text) return '';
    if (window.marked) {
        try {
            return marked.parse(text);
        } catch (e) {
            return escapeHtml(text).replace(/\n/g, '<br>');
        }
    }
    return escapeHtml(text).replace(/\n/g, '<br>');
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        dom.messagesContainer.scrollTop = dom.messagesContainer.scrollHeight;
    });
}

function showWelcomeScreen() {
    dom.welcomeScreen.style.display = 'flex';
}

function hideWelcomeScreen() {
    dom.welcomeScreen.style.display = 'none';
}

// ─── Artifact Panel ────────────────────────────────────────
function showArtifact(artifact) {
    dom.artifactPanel.classList.remove('hidden');
    renderArtifactTabs();
    renderArtifactContent(artifact);
}

window.showArtifactById = function (artifactId) {
    const artifact = state.artifacts.find((a) => a.id === artifactId);
    if (artifact) showArtifact(artifact);
};

function renderArtifactTabs() {
    dom.artifactTabs.innerHTML = '';
    state.artifacts.forEach((a, i) => {
        const tab = document.createElement('button');
        tab.className = `artifact-tab${i === state.artifacts.length - 1 ? ' active' : ''}`;
        tab.textContent = a.title || `Artifact ${i + 1}`;
        tab.addEventListener('click', () => {
            document.querySelectorAll('.artifact-tab').forEach((t) => t.classList.remove('active'));
            tab.classList.add('active');
            renderArtifactContent(a);
        });
        dom.artifactTabs.appendChild(tab);
    });
}

function renderArtifactContent(artifact) {
    dom.artifactContent.innerHTML = '';

    if (artifact.type === 'html') {
        const iframe = document.createElement('iframe');
        iframe.sandbox = 'allow-scripts allow-same-origin';
        iframe.srcdoc = artifact.content;
        iframe.style.width = '100%';
        iframe.style.height = '100%';
        iframe.style.border = 'none';
        iframe.style.background = 'white';
        dom.artifactContent.appendChild(iframe);
    } else {
        // Markdown
        const div = document.createElement('div');
        div.className = 'markdown-render';
        div.innerHTML = renderMarkdown(artifact.content);
        dom.artifactContent.appendChild(div);
    }

    // Store current artifact for copy
    dom.artifactContent.dataset.currentContent = artifact.content;
}

function toggleArtifactPanel() {
    if (dom.artifactPanel.classList.contains('hidden')) {
        dom.artifactPanel.classList.remove('hidden');
        if (state.artifacts.length > 0) {
            renderArtifactTabs();
            renderArtifactContent(state.artifacts[state.artifacts.length - 1]);
        }
    } else {
        closeArtifactPanel();
    }
}

function closeArtifactPanel() {
    dom.artifactPanel.classList.add('hidden');
}

function copyArtifactContent() {
    const content = dom.artifactContent.dataset.currentContent;
    if (content) {
        navigator.clipboard.writeText(content).then(() => {
            showToast('Copied to clipboard!', 'success');
        });
    }
}

// ─── Sidebar ───────────────────────────────────────────────
function toggleSidebar() {
    dom.sidebar.classList.toggle('collapsed');
}

// ─── Settings ──────────────────────────────────────────────
async function loadConfig() {
    try {
        const config = await api.getConfig();
        state.currentProvider = config.llm_provider;
        dom.providerLabel.textContent = providerDisplayName(config.llm_provider);
        dom.modelInput.value = config.model_name || '';
        updateProviderCards(config.llm_provider);
    } catch (e) {
        console.warn('Could not load config (backend may not be running):', e.message);
    }
}

function openSettings() {
    dom.settingsModal.classList.remove('hidden');
    dom.connectionStatus.style.display = 'none';
    updateApiKeyVisibility();
}

function closeSettings() {
    dom.settingsModal.classList.add('hidden');
}

function selectProvider(provider) {
    state.currentProvider = provider;
    updateProviderCards(provider);
    updateApiKeyVisibility();

    // Set default model names
    const defaults = {
        ollama: 'llama3.1:8b',
        anthropic: 'claude-sonnet-4-20250514',
        openai: 'gpt-4o-mini',
    };
    dom.modelInput.value = defaults[provider] || '';
}

function updateProviderCards(active) {
    document.querySelectorAll('.provider-card').forEach((card) => {
        card.classList.toggle('active', card.dataset.provider === active);
    });
}

function updateApiKeyVisibility() {
    dom.apiKeyGroup.style.display = state.currentProvider !== 'ollama' ? 'block' : 'none';
}

async function testConnection() {
    dom.connectionStatus.style.display = 'none';
    dom.testConnectionBtn.textContent = 'Testing...';
    dom.testConnectionBtn.disabled = true;

    try {
        const result = await api.healthCheck();
        dom.connectionStatus.className = `connection-status ${result.status === 'healthy' ? 'success' : 'error'}`;
        dom.connectionStatus.textContent = result.status === 'healthy'
            ? `✅ Connected to ${providerDisplayName(result.provider)} (${result.model})`
            : `❌ ${result.error || 'Connection failed'}`;
        dom.connectionStatus.style.display = 'block';
    } catch (e) {
        dom.connectionStatus.className = 'connection-status error';
        dom.connectionStatus.textContent = `❌ ${e.message}`;
        dom.connectionStatus.style.display = 'block';
    }

    dom.testConnectionBtn.textContent = 'Test Connection';
    dom.testConnectionBtn.disabled = false;
}

async function saveSettings() {
    dom.saveSettingsBtn.textContent = 'Saving...';
    dom.saveSettingsBtn.disabled = true;

    try {
        const config = await api.updateConfig(
            state.currentProvider,
            dom.modelInput.value || null,
            dom.apiKeyInput.value || null,
        );
        dom.providerLabel.textContent = providerDisplayName(config.llm_provider);
        closeSettings();
        showToast(`Switched to ${providerDisplayName(config.llm_provider)}`, 'success');
    } catch (e) {
        showToast(`Failed to save: ${e.message}`, 'error');
    }

    dom.saveSettingsBtn.textContent = 'Save Changes';
    dom.saveSettingsBtn.disabled = false;
}

function providerDisplayName(provider) {
    return { ollama: 'Ollama', anthropic: 'Claude', openai: 'OpenAI' }[provider] || provider;
}

// ─── Utilities ─────────────────────────────────────────────
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed; bottom: 24px; right: 24px; z-index: 2000;
        padding: 12px 20px; border-radius: 10px;
        font-family: var(--font-sans); font-size: 0.85rem;
        color: white; animation: fadeInUp 0.3s ease-out;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        background: ${type === 'error' ? '#dc2626' : type === 'success' ? '#059669' : '#6c5ce7'};
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

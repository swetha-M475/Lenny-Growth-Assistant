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
    currentArtifactMode: 'preview', // 'preview', 'code', 'split'
    activeArtifact: null,           // Current selected artifact
};

// ─── DOM Elements ──────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const dom = {
    sidebar: $('sidebar'),
    sidebarToggle: $('sidebar-toggle'),
    newChatBtn: $('new-chat-btn'),
    sessionsList: $('sessions-list'),
    chatTitle: $('chat-title'),
    chatArea: $('chat-area'),
    messagesContainer: $('messages-container'),
    welcomeScreen: $('welcome-screen'),
    chatInput: $('chat-input'),
    sendBtn: $('send-btn'),
    skillSelect: $('skill-select'),
    
    // Splitters
    chatArtifactSplitter: $('chat-artifact-splitter'),
    artifactSplitSplitter: $('artifact-split-splitter'),
    
    // Artifact Viewport
    artifactPanel: $('artifact-panel'),
    artifactContent: $('artifact-content'),
    artifactViewport: $('artifact-viewport'),
    artifactTabs: $('artifact-tabs'),
    artifactToggleBtn: $('artifact-toggle-btn'),
    
    // Panes
    artifactPreviewPane: $('artifact-preview-pane'),
    artifactIframe: $('artifact-iframe'),
    artifactCodePane: $('artifact-code-pane'),
    artifactCodeBlock: $('artifact-code-block'),
    lineNumbers: $('line-numbers'),
    artifactMarkdownPane: $('artifact-markdown-pane'),
    artifactMarkdownRender: $('artifact-markdown-render'),
    
    // Toolbar buttons
    artifactViewModes: $('artifact-view-modes'),
    modePreview: $('mode-preview'),
    modeCode: $('mode-code'),
    modeSplit: $('mode-split'),
    artifactRefreshBtn: $('artifact-refresh-btn'),
    artifactCopyBtn: $('artifact-copy-btn'),
    artifactDownloadHtmlBtn: $('artifact-download-html-btn'),
    artifactDownloadZipBtn: $('artifact-download-zip-btn'),
    artifactFullscreenBtn: $('artifact-fullscreen-btn'),
    artifactCloseBtn: $('artifact-close-btn'),
    
    // Settings
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
    voiceBtn: $('voice-btn'),

    // Fullscreen view modal
    fullscreenArtifactModal: $('fullscreen-artifact-modal'),
    fullscreenModalTitle: $('fullscreen-modal-title'),
    fullscreenRefreshBtn: $('fullscreen-refresh-btn'),
    fullscreenCloseBtn: $('fullscreen-close-btn'),
    fullscreenModalBody: $('fullscreen-modal-body'),
};

// ─── Initialize ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();
    await loadConfig();
    await loadSessions();

    // Configure marked.js for Markdown rendering
    if (window.marked) {
        const { markedHighlight } = window.markedHighlight;
        marked.use(markedHighlight({
            langPrefix: 'hljs language-',
            highlight(code, lang) {
                if (window.hljs && lang && hljs.getLanguage(lang)) {
                    return hljs.highlight(code, { language: lang }).value;
                }
                if (window.hljs) {
                    return hljs.highlightAuto(code).value;
                }
                return code;
            }
        }));
        marked.use({
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

    // Voice Search
    initVoiceSearch();

    // Suggestion Chips
    document.querySelectorAll('.suggestion-chip').forEach((chip) => {
        chip.addEventListener('click', () => {
            dom.chatInput.value = chip.dataset.prompt;
            handleInputChange();
            sendMessage();
        });
    });

    // Panel controls
    dom.artifactCloseBtn.addEventListener('click', closeArtifactPanel);
    dom.artifactToggleBtn.addEventListener('click', toggleArtifactPanel);

    // View Modes Toggles
    dom.modePreview.addEventListener('click', () => setArtifactMode('preview'));
    dom.modeCode.addEventListener('click', () => setArtifactMode('code'));
    dom.modeSplit.addEventListener('click', () => setArtifactMode('split'));

    // Action Toolbar buttons
    dom.artifactRefreshBtn.addEventListener('click', refreshArtifactPreview);
    dom.artifactCopyBtn.addEventListener('click', copyArtifactContent);
    dom.artifactDownloadHtmlBtn.addEventListener('click', downloadArtifactHtml);
    dom.artifactDownloadZipBtn.addEventListener('click', downloadArtifactZip);
    dom.artifactFullscreenBtn.addEventListener('click', openFullscreenArtifact);

    // Fullscreen modal listeners
    dom.fullscreenCloseBtn.addEventListener('click', closeFullscreenArtifact);
    dom.fullscreenRefreshBtn.addEventListener('click', refreshFullscreenPreview);
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeFullscreenArtifact();
            closeSettings();
        }
    });

    // Initialize Resize Splitters drag support
    initResizeSplitters();

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

// ─── Voice Search ──────────────────────────────────────────
function initVoiceSearch() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        dom.voiceBtn.classList.add('unsupported');
        dom.voiceBtn.title = 'Voice search not supported in this browser';
        dom.voiceBtn.disabled = true;
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    let isListening = false;
    let finalTranscript = '';

    recognition.onstart = () => {
        isListening = true;
        finalTranscript = '';
        dom.voiceBtn.classList.add('listening');
        dom.voiceBtn.title = 'Listening… click to stop';
    };

    recognition.onresult = (event) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += transcript;
            } else {
                interim += transcript;
            }
        }
        // Show live interim text in the input as user speaks
        dom.chatInput.value = finalTranscript + interim;
        // Manually enable send button since programmatic value changes don't fire the input event
        dom.sendBtn.disabled = false;
        dom.chatInput.style.height = 'auto';
        dom.chatInput.style.height = Math.min(dom.chatInput.scrollHeight, 200) + 'px';
    };

    recognition.onend = () => {
        isListening = false;
        dom.voiceBtn.classList.remove('listening');
        dom.voiceBtn.title = 'Click to speak';
        const text = finalTranscript.trim();
        if (text) {
            dom.chatInput.value = text;
            dom.sendBtn.disabled = false;
            // Auto-send the recognized speech
            sendMessage();
        }
    };

    recognition.onerror = (event) => {
        isListening = false;
        dom.voiceBtn.classList.remove('listening');
        dom.voiceBtn.title = 'Click to speak';
        if (event.error !== 'aborted' && event.error !== 'no-speech') {
            showToast(`Voice error: ${event.error}`, 'error');
        }
    };

    dom.voiceBtn.addEventListener('click', () => {
        if (state.isStreaming) return;
        if (isListening) {
            recognition.stop();
        } else {
            dom.chatInput.value = '';
            handleInputChange();
            recognition.start();
        }
    });
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
    const container = dom.messagesContainer;

    // Clear previous message elements first
    const existing = container.querySelectorAll('.message');
    existing.forEach((el) => el.remove());

    if (state.messages.length === 0) {
        showWelcomeScreen();
        return;
    }

    hideWelcomeScreen();

    state.messages.forEach((msg) => {
        const el = createMessageElement(msg);
        container.appendChild(el);
    });

    scrollToBottom();
}

function extractFrontendArtifacts(msg) {
    if (msg.role !== 'assistant') return;

    if (!msg.artifacts) msg.artifacts = [];

    // 1. Extract XML <artifact> tags (case-insensitive, handles multiline attributes)
    const artifactRegex = /<artifact\s+type=["'](html|markdown)["']\s+title=["']([^"']*)["']\s*>([\s\S]*?)<\/artifact>/gi;
    let match;
    const contentToParse = msg.content;

    while ((match = artifactRegex.exec(contentToParse)) !== null) {
        const [, type, title, content] = match;
        const cleanTitle = title.trim();
        if (!msg.artifacts.some(a => a.title === cleanTitle)) {
            const art = {
                id: 'fe-' + Math.random().toString(36).substr(2, 9),
                type: type.toLowerCase(),
                title: cleanTitle,
                content: content.trim()
            };
            msg.artifacts.push(art);
            if (!state.artifacts.some(a => a.title === cleanTitle)) {
                state.artifacts.push(art);
            }
        }
    }

    // 2. Fallback: Parse fenced code blocks for HTML (runs even if some XML tags were found,
    //    in case the LLM mixed both formats)
    const hasHtmlArtifact = msg.artifacts.some(a => a.type === 'html');
    if (!hasHtmlArtifact) {
        const codeBlockRegex = /```(html|xml|svg)?\s*([\s\S]*?)```/gi;
        const htmlBlocks = [];
        const cssBlocks = [];
        const jsBlocks = [];

        while ((match = codeBlockRegex.exec(contentToParse)) !== null) {
            const lang = (match[1] || '').toLowerCase();
            const content = match[2].trim();

            if (lang === 'html' || lang === 'xml' || lang === 'svg') {
                htmlBlocks.push(content);
            } else if (lang === 'css') {
                cssBlocks.push(content);
            } else if (lang === 'js' || lang === 'javascript') {
                jsBlocks.push(content);
            } else {
                // Sniff content only if language tag is missing
                if (content.includes('<html') || content.includes('<!DOCTYPE') || content.includes('<!doctype')) {
                    htmlBlocks.push(content);
                } else if ((content.includes('<div') || content.includes('<svg') || content.includes('<section')) && content.includes('<style')) {
                    htmlBlocks.push(content);
                } else if (content.includes('body {') || (content.includes('margin:') && content.includes('padding:'))) {
                    cssBlocks.push(content);
                } else if (content.includes('function ') || content.includes('document.') || content.includes('const ')) {
                    jsBlocks.push(content);
                }
            }
        }

        if (htmlBlocks.length > 0) {
            const mainHtml = htmlBlocks.join('\n');
            const cssContent = cssBlocks.join('\n');
            const jsContent = jsBlocks.join('\n');

            let combinedContent = '';

            if (mainHtml.includes('<html') || mainHtml.includes('<!DOCTYPE') || mainHtml.includes('<!doctype')) {
                combinedContent = mainHtml;
                if (cssContent) {
                    if (combinedContent.includes('</head>')) {
                        combinedContent = combinedContent.replace('</head>', `<style>\n${cssContent}\n</style>\n</head>`);
                    } else {
                        combinedContent = `<style>\n${cssContent}\n</style>\n` + combinedContent;
                    }
                }
                if (jsContent) {
                    if (combinedContent.includes('</body>')) {
                        combinedContent = combinedContent.replace('</body>', `<script>\n${jsContent}\n</script>\n</body>`);
                    } else {
                        combinedContent = combinedContent + `\n<script>\n${jsContent}\n</script>`;
                    }
                }
            } else {
                combinedContent = `<!DOCTYPE html>\n<html>\n<head>\n    <meta charset="utf-8">\n    <title>Visualization</title>\n    <style>\n        body { font-family: -apple-system, sans-serif; margin: 0; padding: 24px; background: #0f172a; color: #f1f5f9; }\n        ${cssContent}\n    </style>\n</head>\n<body>\n    ${mainHtml}\n    <script>\n        document.addEventListener('DOMContentLoaded', () => { ${jsContent} });\n    </script>\n</body>\n</html>`;
            }

            const art = {
                id: 'fe-combined-' + Math.random().toString(36).substr(2, 9),
                type: 'html',
                title: 'HTML Interactive Dashboard',
                content: combinedContent
            };
            msg.artifacts.push(art);
            state.artifacts.push(art);
        }
    }
}

function createMessageElement(msg) {
    // Extract any visual artifacts on-the-fly from raw content
    extractFrontendArtifacts(msg);

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
        // Strip XML artifacts from the chat bubble
        let cleanContent = msg.content.replace(/<artifact[^>]*>[\s\S]*?<\/artifact>/gi, '').trim();
        // Strip raw HTML code blocks if they were extracted to side panel
        if (msg.artifacts && msg.artifacts.length > 0) {
            cleanContent = cleanContent.replace(/```html[\s\S]*?```/gi, '').trim();
            cleanContent = cleanContent.replace(/```xml[\s\S]*?```/gi, '').trim();
            cleanContent = cleanContent.replace(/```svg[\s\S]*?```/gi, '').trim();
            
            // Strip raw HTML that leaked outside artifact/code-block wrappers
            const withoutCodeBlocks = cleanContent.replace(/```[\s\S]*?```/g, '');
            if (withoutCodeBlocks.includes('<!DOCTYPE') || withoutCodeBlocks.includes('<html') || withoutCodeBlocks.includes('<!doctype')) {
                // Find the position of the first HTML tag and truncate
                const firstHtmlTag = Math.min(
                    cleanContent.indexOf('<!DOCTYPE') !== -1 ? cleanContent.indexOf('<!DOCTYPE') : Infinity,
                    cleanContent.indexOf('<html') !== -1 ? cleanContent.indexOf('<html') : Infinity,
                    cleanContent.indexOf('<!doctype') !== -1 ? cleanContent.indexOf('<!doctype') : Infinity,
                );
                if (firstHtmlTag !== Infinity) {
                    cleanContent = cleanContent.substring(0, firstHtmlTag).trim();
                }
            }
        }
        // Strip incomplete <artifact open tags if the response was truncated
        const partialIdx = cleanContent.indexOf('<artifact');
        if (partialIdx !== -1) {
            cleanContent = cleanContent.substring(0, partialIdx).trim();
        }
        renderedContent = renderMarkdown(cleanContent) || '<em>Generated an interactive artifact \u2192</em>';
    } else {
        renderedContent = escapeHtml(msg.content);
    }

    // Build artifact notice box and view button
    let artifactCardHtml = '';
    if (msg.artifacts && msg.artifacts.length > 0) {
        msg.artifacts.forEach((a) => {
            artifactCardHtml += `
                <div class="artifact-card-notice">
                    <span class="artifact-check-icon">✅</span>
                    <span><strong>${escapeHtml(a.title || 'Artifact')}</strong> — Your artifact is ready! Click the button below to open it.</span>
                </div>
                <button class="view-artifact-btn" data-artifact-id="${a.id}" onclick="showArtifactById('${a.id}')">
                    <span class="artifact-btn-icon">📑</span>
                    View Artifact: ${escapeHtml(a.title || 'View Artifact')}
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
            ${artifactCardHtml}
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
    let cleanContent = msg.content;

    // Strip completed <artifact>...</artifact> blocks
    cleanContent = cleanContent.replace(/<artifact[^>]*>[\s\S]*?<\/artifact>/gi, '').trim();

    // Strip partial/in-progress <artifact ...> open tag and everything after it
    // (this prevents raw HTML from leaking into the chat during streaming)
    const partialArtifactIdx = cleanContent.indexOf('<artifact');
    if (partialArtifactIdx !== -1) {
        cleanContent = cleanContent.substring(0, partialArtifactIdx).trim();
        // Show a generating indicator
        cleanContent += '\n\n✨ *Generating interactive artifact...*';
    }

    // Also detect raw HTML that's NOT inside artifact tags (fenced code block HTML)
    // If the skill is 'artifact' and we see raw HTML tags building up, suppress them
    if (msg.skill_used === 'artifact' && !cleanContent.includes('<artifact')) {
        // Check if the content contains substantial raw HTML (not in markdown code blocks)
        const rawHtmlCheck = cleanContent.replace(/```[\s\S]*?```/g, '');
        if (rawHtmlCheck.includes('<!DOCTYPE') || rawHtmlCheck.includes('<html') || 
            (rawHtmlCheck.includes('<style>') && rawHtmlCheck.includes('<body'))) {
            // Strip everything from the first HTML tag onward
            const htmlStart = Math.min(
                rawHtmlCheck.indexOf('<!DOCTYPE') !== -1 ? rawHtmlCheck.indexOf('<!DOCTYPE') : Infinity,
                rawHtmlCheck.indexOf('<html') !== -1 ? rawHtmlCheck.indexOf('<html') : Infinity,
                rawHtmlCheck.indexOf('<!doctype') !== -1 ? rawHtmlCheck.indexOf('<!doctype') : Infinity
            );
            if (htmlStart !== Infinity) {
                cleanContent = cleanContent.substring(0, htmlStart).trim();
                cleanContent += '\n\n✨ *Generating interactive artifact...*';
            }
        }
    }

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
let currentBlobUrl = null;

function showArtifact(artifact) {
    state.activeArtifact = artifact;
    dom.artifactPanel.classList.remove('hidden');
    dom.chatArtifactSplitter.classList.remove('hidden');

    // Align panels with current custom property width
    const chatPane = dom.chatArea;
    chatPane.style.width = `calc(100% - var(--artifact-width))`;

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
        tab.className = `artifact-tab${a.id === state.activeArtifact?.id ? ' active' : ''}`;
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
    state.activeArtifact = artifact;
    
    // Re-highlight target tab in case tabs list updated
    const tabs = dom.artifactTabs.querySelectorAll('.artifact-tab');
    state.artifacts.forEach((a, idx) => {
        if (a.id === artifact.id && tabs[idx]) {
            tabs.forEach(t => t.classList.remove('active'));
            tabs[idx].classList.add('active');
        }
    });

    const type = artifact.type || artifact.artifact_type;
    
    if (type === 'html') {
        refreshArtifactPreview();
        renderArtifactCode(artifact);
        setArtifactMode(state.currentArtifactMode || 'preview');
    } else {
        // Markdown Rendering
        const renderDiv = dom.artifactMarkdownRender;
        renderDiv.innerHTML = renderMarkdown(artifact.content);
        setArtifactMode('markdown');
    }

    // Store raw content for copy / export actions
    dom.artifactContent.dataset.currentContent = artifact.content;
}

function setArtifactMode(mode) {
    if (!state.activeArtifact) return;

    state.currentArtifactMode = mode;

    // Toggle active tabs style
    dom.modePreview.classList.toggle('active', mode === 'preview');
    dom.modeCode.classList.toggle('active', mode === 'code');
    dom.modeSplit.classList.toggle('active', mode === 'split');

    // Remove mode classes
    dom.artifactViewport.classList.remove('mode-preview', 'mode-code', 'mode-split', 'mode-markdown');

    const type = state.activeArtifact.type || state.activeArtifact.artifact_type;
    if (type !== 'html') {
        dom.artifactViewport.classList.add('mode-markdown');
        dom.artifactViewModes.style.display = 'none';
        dom.artifactRefreshBtn.style.display = 'none';
        dom.artifactDownloadZipBtn.style.display = 'none';
        dom.artifactDownloadHtmlBtn.style.display = 'none';
        dom.artifactFullscreenBtn.style.display = 'none';
    } else {
        dom.artifactViewport.classList.add(`mode-${mode}`);
        dom.artifactViewModes.style.display = 'flex';
        dom.artifactRefreshBtn.style.display = 'flex';
        dom.artifactDownloadZipBtn.style.display = 'flex';
        dom.artifactDownloadHtmlBtn.style.display = 'flex';
        dom.artifactFullscreenBtn.style.display = 'flex';

        // Reset splitter positions to 50/50 in split mode
        if (mode === 'split') {
            dom.artifactPreviewPane.style.width = '50%';
            dom.artifactCodePane.style.width = 'calc(50% - 6px)';
        }
    }
}

function renderArtifactCode(artifact) {
    const codeBlock = dom.artifactCodeBlock;
    codeBlock.textContent = artifact.content;

    // Syntax highlight code block
    if (window.hljs) {
        hljs.highlightElement(codeBlock);
    }

    // Populate line numbers sidebar
    generateLineNumbers(artifact.content);
}

function generateLineNumbers(code) {
    const linesContainer = dom.lineNumbers;
    linesContainer.innerHTML = '';
    const lines = code.split('\n');
    lines.forEach((_, idx) => {
        const span = document.createElement('span');
        span.textContent = idx + 1;
        linesContainer.appendChild(span);
    });
}

function refreshArtifactPreview() {
    if (!state.activeArtifact) return;

    if (currentBlobUrl) {
        URL.revokeObjectURL(currentBlobUrl);
    }

    const type = state.activeArtifact.type || state.activeArtifact.artifact_type;
    if (type === 'html') {
        let content = state.activeArtifact.content;

        // Theme Safety Net: If generated HTML lacks explicit dark background styling,
        // inject a default glassmorphic dark design system into <head> so it never renders plain white
        const defaultDarkTheme = `
    <style id="theme-fallback">
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        * { box-sizing: border-box; }
        html, body {
            background: #0f172a !important;
            color: #f1f5f9 !important;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            margin: 0;
            padding: 24px;
            min-height: 100vh;
        }
        h1, h2, h3, h4 {
            color: #38bdf8 !important;
            font-weight: 700;
            margin-top: 0;
            margin-bottom: 12px;
        }
        p { color: #cbd5e1; line-height: 1.6; margin-bottom: 12px; }
        ul, ol { padding-left: 20px; line-height: 1.8; color: #cbd5e1; margin-bottom: 16px; }
        li { margin-bottom: 6px; }
        button, .btn, .cta {
            background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
            color: #ffffff !important;
            border: none !important;
            padding: 10px 20px !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            cursor: pointer !important;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4) !important;
            transition: all 0.2s ease !important;
        }
        button:hover, .btn:hover, .cta:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6) !important;
        }
        .section, .card, .box, section, div:has(> h2), div:has(> h3) {
            background: rgba(30, 41, 59, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
            backdrop-filter: blur(12px);
        }
    </style>`;

        const hasBackgroundStyle = content.includes('background:') || content.includes('background-color:');
        if (!hasBackgroundStyle) {
            if (content.includes('</head>')) {
                content = content.replace('</head>', `${defaultDarkTheme}\n</head>`);
            } else if (content.includes('<html>')) {
                content = content.replace('<html>', `<html>\n<head>${defaultDarkTheme}</head>`);
            } else {
                content = `<!DOCTYPE html>\n<html>\n<head>${defaultDarkTheme}</head>\n<body>\n${content}\n</body>\n</html>`;
            }
        }

        const blob = new Blob([content], { type: 'text/html' });
        currentBlobUrl = URL.createObjectURL(blob);
        dom.artifactIframe.src = currentBlobUrl;
    }
}

function copyArtifactContent() {
    if (!state.activeArtifact) return;
    navigator.clipboard.writeText(state.activeArtifact.content).then(() => {
        showToast('Code copied to clipboard!', 'success');
    });
}

function downloadArtifactHtml() {
    if (!state.activeArtifact) return;
    const title = state.activeArtifact.title || 'visualization';
    const filename = `${title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.html`;

    const blob = new Blob([state.activeArtifact.content], { type: 'text/html' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();

    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`Downloaded HTML: ${filename}`, 'success');
}

function downloadArtifactZip() {
    if (!state.activeArtifact) return;
    if (!window.JSZip) {
        showToast('ZIP packaging requires JSZip script to load.', 'error');
        return;
    }

    const title = state.activeArtifact.title || 'app';
    const rawHtml = state.activeArtifact.content;

    let cssContent = '';
    let jsContent = '';

    // Extract inline stylesheet contents
    const styleRegex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
    let styleMatch;
    while ((styleMatch = styleRegex.exec(rawHtml)) !== null) {
        cssContent += styleMatch[1].trim() + '\n\n';
    }

    // Extract inline javascript contents (excluding external CDN script tags)
    const scriptRegex = /<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/gi;
    let scriptMatch;
    while ((scriptMatch = scriptRegex.exec(rawHtml)) !== null) {
        jsContent += scriptMatch[1].trim() + '\n\n';
    }

    // Construct cleaned HTML page linked to separate assets
    let cleanedHtml = rawHtml;
    cleanedHtml = cleanedHtml.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');
    if (cssContent.trim()) {
        if (cleanedHtml.includes('</head>')) {
            cleanedHtml = cleanedHtml.replace('</head>', '    <link rel="stylesheet" href="style.css">\n</head>');
        } else {
            cleanedHtml = '<link rel="stylesheet" href="style.css">\n' + cleanedHtml;
        }
    }

    cleanedHtml = cleanedHtml.replace(/<script(?![^>]*src=)[^>]*>[\s\S]*?<\/script>/gi, '');
    if (jsContent.trim()) {
        if (cleanedHtml.includes('</body>')) {
            cleanedHtml = cleanedHtml.replace('</body>', '    <script src="script.js"></script>\n</body>');
        } else {
            cleanedHtml = cleanedHtml + '\n<script src="script.js"></script>';
        }
    }

    // Package ZIP package asynchronously
    const zip = new JSZip();
    zip.file("index.html", cleanedHtml);
    if (cssContent.trim()) {
        zip.file("style.css", cssContent.trim());
    }
    if (jsContent.trim()) {
        zip.file("script.js", jsContent.trim());
    }

    zip.generateAsync({ type: "blob" }).then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const zipName = `${title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.zip`;
        a.download = zipName;
        document.body.appendChild(a);
        a.click();

        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast(`Downloaded ZIP: ${zipName}`, 'success');
    }).catch((e) => {
        console.error('ZIP compilation error:', e);
        showToast('Failed to package ZIP archive.', 'error');
    });
}

function openFullscreenArtifact() {
    if (!state.activeArtifact) return;

    dom.fullscreenArtifactModal.classList.remove('hidden');
    dom.fullscreenModalTitle.textContent = state.activeArtifact.title || 'Preview';
    dom.fullscreenModalBody.innerHTML = '';

    const type = state.activeArtifact.type || state.activeArtifact.artifact_type;
    if (type === 'html') {
        if (!currentBlobUrl) {
            const blob = new Blob([state.activeArtifact.content], { type: 'text/html' });
            currentBlobUrl = URL.createObjectURL(blob);
        }
        const iframe = document.createElement('iframe');
        iframe.sandbox = 'allow-scripts allow-same-origin allow-popups allow-forms';
        iframe.src = currentBlobUrl;
        iframe.style.width = '100%';
        iframe.style.height = '100%';
        iframe.style.border = 'none';
        
        dom.fullscreenModalBody.appendChild(iframe);
        dom.fullscreenRefreshBtn.style.display = 'block';
    } else {
        const div = document.createElement('div');
        div.className = 'markdown-render';
        div.style.padding = 'var(--space-xl)';
        div.style.background = 'var(--bg-deepest)';
        div.style.color = 'var(--text-primary)';
        div.style.height = '100%';
        div.style.overflow = 'auto';
        div.innerHTML = renderMarkdown(state.activeArtifact.content);
        
        dom.fullscreenModalBody.appendChild(div);
        dom.fullscreenRefreshBtn.style.display = 'none';
    }
}

function closeFullscreenArtifact() {
    dom.fullscreenArtifactModal.classList.add('hidden');
    dom.fullscreenModalBody.innerHTML = '';
}

function refreshFullscreenPreview() {
    const iframe = dom.fullscreenModalBody.querySelector('iframe');
    if (iframe && currentBlobUrl) {
        iframe.src = '';
        iframe.src = currentBlobUrl;
    }
}

function toggleArtifactPanel() {
    if (dom.artifactPanel.classList.contains('hidden')) {
        if (state.artifacts.length > 0) {
            showArtifact(state.activeArtifact || state.artifacts[state.artifacts.length - 1]);
        }
    } else {
        closeArtifactPanel();
    }
}

function closeArtifactPanel() {
    dom.artifactPanel.classList.add('hidden');
    dom.chatArtifactSplitter.classList.add('hidden');
    dom.chatArea.style.width = '100%';
}

/* ─── Panel Resizer Splitting ────────────────────────────────── */
function initResizeSplitters() {
    const chatSplitter = dom.chatArtifactSplitter;
    const chatArea = dom.chatArea;
    const panel = dom.artifactPanel;
    const container = document.querySelector('.main-content');

    let startX, startLeftWidth, startRightWidth;

    chatSplitter.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        startX = e.clientX;
        startLeftWidth = chatArea.getBoundingClientRect().width;
        startRightWidth = panel.getBoundingClientRect().width;

        chatSplitter.classList.add('active');
        document.body.classList.add('resizing');

        window.addEventListener('pointermove', onSplitterMove);
        window.addEventListener('pointerup', onSplitterUp);
    });

    function onSplitterMove(e) {
        const deltaX = e.clientX - startX;
        const newLeftWidth = startLeftWidth + deltaX;
        const newRightWidth = startRightWidth - deltaX;
        const totalWidth = container.getBoundingClientRect().width;

        // Apply width parameters within constraints
        if (newLeftWidth > 320 && newRightWidth > 320) {
            const rightPercent = (newRightWidth / totalWidth) * 100;
            chatArea.style.width = `calc(100% - ${rightPercent}%)`;
            panel.style.width = `${rightPercent}%`;
            document.documentElement.style.setProperty('--artifact-width', `${rightPercent}%`);
        }
    }

    function onSplitterUp() {
        chatSplitter.classList.remove('active');
        document.body.classList.remove('resizing');
        window.removeEventListener('pointermove', onSplitterMove);
        window.removeEventListener('pointerup', onSplitterUp);
    }

    // Inner preview/code view splitter resizing
    const innerSplitter = dom.artifactSplitSplitter;
    const previewPane = dom.artifactPreviewPane;
    const codePane = dom.artifactCodePane;
    const viewport = dom.artifactViewport;

    let innerStartX, startPreviewWidth, startCodeWidth;

    innerSplitter.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        innerStartX = e.clientX;
        startPreviewWidth = previewPane.getBoundingClientRect().width;
        startCodeWidth = codePane.getBoundingClientRect().width;

        innerSplitter.classList.add('active');
        document.body.classList.add('resizing');

        window.addEventListener('pointermove', onInnerSplitterMove);
        window.addEventListener('pointerup', onInnerSplitterUp);
    });

    function onInnerSplitterMove(e) {
        const deltaX = e.clientX - innerStartX;
        const newPreviewWidth = startPreviewWidth + deltaX;
        const newCodeWidth = startCodeWidth - deltaX;
        const totalWidth = viewport.getBoundingClientRect().width;

        if (newPreviewWidth > 150 && newCodeWidth > 150) {
            const previewPercent = (newPreviewWidth / totalWidth) * 100;
            previewPane.style.width = `${previewPercent}%`;
            codePane.style.width = `calc(100% - ${previewPercent}% - 6px)`;
        }
    }

    function onInnerSplitterUp() {
        innerSplitter.classList.remove('active');
        document.body.classList.remove('resizing');
        window.removeEventListener('pointermove', onInnerSplitterMove);
        window.removeEventListener('pointerup', onInnerSplitterUp);
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

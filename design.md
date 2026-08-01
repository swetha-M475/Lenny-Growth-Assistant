# UI/UX Design Document
## The Lenny Growth Assistant

---

## 1. Design Philosophy

The Lenny Growth Assistant is designed to feel like a **premium, professional AI workspace** — taking inspiration from ChatGPT's clean conversational interface and Claude's side-by-side artifact viewer. Every design decision prioritizes **clarity, speed, and delight**.

### Core Principles:
- **Dark-first design** — Reduces eye strain for long sessions, feels premium
- **Content hierarchy** — The conversation is king; chrome is minimal
- **Progressive disclosure** — Advanced features (skills, settings) appear only when needed
- **Micro-interactions** — Subtle animations create a sense of life and responsiveness
- **Glassmorphism** — Frosted glass effects add depth without cluttering

---

## 2. Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--bg-deepest` | `#06060a` | Page background |
| `--bg-base` | `#0c0c14` | Sidebar background |
| `--bg-surface` | `#12121e` | Cards, input fields |
| `--bg-elevated` | `#1a1a2e` | Hover states, modals |
| `--accent-primary` | `#7c6cf0` | Buttons, active states, links |
| `--accent-secondary` | `#a78bfa` | Bold text in responses, highlights |
| `--text-primary` | `#f0eef6` | Main text |
| `--text-secondary` | `#9e9cb5` | Muted text, labels |
| `--success` | `#4ade80` | Healthy connection indicator |
| `--error` | `#f87171` | Error states |

The palette avoids generic blue/green and instead uses a **deep navy-to-violet spectrum** that feels sophisticated and distinctly non-generic.

---

## 3. Typography

| Element | Font | Weight | Size |
|---------|------|--------|------|
| Body text | Inter | 400 | 0.9rem |
| Headers | Inter | 700-800 | 1.1-1.75rem |
| Code | JetBrains Mono | 400 | 0.85rem |
| Labels | Inter | 600 | 0.82rem |
| Hints | Inter | 400 | 0.7rem |

**Inter** was chosen for its excellent readability at all sizes and its neutral, professional character. **JetBrains Mono** provides clean code rendering.

---

## 4. Layout Architecture

```
┌────────────────────────────────────────────────────────┐
│                                                        │
│  ┌─────────┐  ┌────────────────┐  ┌─────────────────┐ │
│  │         │  │                │  │                 │ │
│  │ Sidebar │  │   Chat Area    │  │  Artifact Panel │ │
│  │ 280px   │  │   flex: 1      │  │    50%          │ │
│  │         │  │                │  │  (collapsible)  │ │
│  │         │  │                │  │                 │ │
│  └─────────┘  └────────────────┘  └─────────────────┘ │
│                                                        │
└────────────────────────────────────────────────────────┘
```

- **Sidebar** (280px): Session list, new chat, settings
- **Chat Area** (flex: 1): Messages + input
- **Artifact Panel** (50%): HTML/Markdown viewer, collapsible

### Responsive Breakpoints:
- **Desktop** (>768px): Full 3-column layout
- **Mobile** (≤768px): Sidebar overlays, artifact panel fullscreen

---

## 5. Component Design

### 5.1 Sidebar
- Gradient accent "New Chat" button with glow shadow
- Session items with hover reveal delete button
- Active session has left-edge accent bar indicator
- Provider badge at bottom shows current LLM status

### 5.2 Welcome Screen
- Centered layout with floating logo animation
- Gradient text title
- 2×2 grid of suggestion chips with hover lift effect
- Disappears after first message

### 5.3 Message Bubbles
- User messages: right-side, subtle surface background with border
- Assistant messages: left-side, clean layout with skill badge
- Skill badges: Color-coded (Q&A=blue, Ship30=orange, Artifact=purple)
- Slide-in animation on new messages

### 5.4 Chat Input
- Full-width input bar with glass-focus ring
- Auto-expanding textarea
- Skill selector dropdown (Auto/Q&A/Essay/Artifact)
- Accent-colored send button with disabled state

### 5.5 Artifact Viewer
- Slides in from right with animation
- Tab bar for multiple artifacts
- HTML rendered in sandboxed iframe
- Markdown rendered with styled typography
- Copy and close action buttons

### 5.6 Settings Modal
- Centered overlay with blur background
- 3-card provider selector (Ollama/Claude/OpenAI) with glow on active
- Model name and API key inputs
- "Test Connection" and "Save Changes" buttons
- Status indicator with color-coded feedback

---

## 6. Micro-Animations

| Interaction | Animation | Duration |
|-------------|-----------|----------|
| New message | Slide up + fade in | 300ms |
| Welcome icon | Floating up/down | 3s infinite |
| Typing indicator | Bouncing dots | 1.4s infinite |
| Streaming text | Blinking cursor | 800ms |
| Modal open | Scale up + fade | 300ms |
| Artifact panel | Slide from right | 300ms |
| Button hover | Lift + shadow grow | 150ms |
| Toast notification | Slide up + auto-dismiss | 3s |

All animations use `cubic-bezier(0.4, 0, 0.2, 1)` for natural feel.

---

## 7. Accessibility

- All interactive elements have clear focus states
- Color contrast meets WCAG AA standard
- Keyboard navigable (Enter to send, Shift+Enter for newline)
- SVG icons include title attributes
- Semantic HTML5 elements (aside, main, nav)

---

## 8. Design Inspiration

- **ChatGPT**: Sidebar session management, input bar design
- **Claude Artifacts**: Side-by-side artifact viewer
- **Linear**: Dark theme sophistication, subtle glass effects
- **Vercel**: Clean typography, minimal chrome

# MAIN SCREENS LAYOUT PLAN

> **Design Direction:** Clean white contrast glassy. Main chat is the centerpiece with quick actions, auto-showing Visualize panel with Siri-style colored border animation, and integration icons across the top for future modules.

> **Read first:** `SPLASH_SCREEN_PLAN.md`, `VISUALIZE_AGENT_PLAN.md`, `V1.2_UI_LAYOUT.md`

---

# PART I — LAYOUT OVERVIEW

## 1. The Full Screen Composition

```
╔════════════════════════════════════════════════════════════════════╗
║ [👤] | [☁][📁][📨][💬][📧][📱][🔵]      [🔍] [🔔] [⚙] [⏻]        ║ ← Top bar
╠══════════╤═══════════════════════════════════╤═══════════════════╣
║          │                                   │                   ║
║  Quick   │      MAIN CHAT VIEW              │  VISUALIZE PANEL ║
║  Actions │      (scrolling, like Claude)    │  (hide/show,     ║
║          │                                   │   auto-shows on  ║
║  ╭────╮  │      ▲ scroll for history        │   related query) ║
║  │P&L │  │                                   │                  ║
║  ╰────╯  │      [Past messages above]        │  ┌────────────┐  ║
║  ╭────╮  │                                   │  │ ◊ VISUALIZE│  ║
║  │Proj│  │      [User] Show P&L              │  │ ━━━━━━━━━━ │  ║
║  ╰────╯  │      [AI] Here's your P&L...     │  │            │  ║
║  ╭────╮  │      [KPI + Chart]               │  │ Drop here  │  ║
║  │Cash│  │      [Suggestions]               │  │            │  ║
║  ╰────╯  │                                   │  │ [Options]  │  ║
║          │      ▼ auto-scroll to latest     │  │            │  ║
║          │                                   │  │ Live anim  │  ║
║          │  ┌─────────────────────────────┐  │  └────────────┘  ║
║          │  │ Type or speak... | [🎤] [→] │  │                  ║
║          │  └─────────────────────────────┘  │                   ║
╚══════════╧═══════════════════════════════════╧═══════════════════╝
   Left              Center                          Right
  Sidebar          (Scrollable)                  (Visualize panel
                                                  auto-show/hide)
```

## 2. Three-Zone System

```
ZONE 1: TOP BAR (fixed)
  - Identity icons (profile, logout)
  - Integration icons (cloud services, comms)
  - Utility icons (search, notifications, settings)

ZONE 2: MAIN AREA (3 columns)
  - LEFT: Quick action pills (always visible)
  - CENTER: Scrolling chat (main interaction)
  - RIGHT: Visualize panel (auto show/hide)

ZONE 3: BOTTOM (within center)
  - Input bar (always at bottom of chat column)
```

---

# PART II — TOP BAR REDESIGN

## 3. Top Bar Layout

```
LEFT GROUP             |  CENTER GROUP                 |  RIGHT GROUP
[👤 Profile]          |  [☁][📁][📨][💬][📧][📱][🔵]  |  [🔍][🔔][⚙][⏻]
[⏻ Logout]            |  Integration apps              |  Utility
```

## 4. Identity Icons (Left)

```
[👤] Profile icon
  Click → opens profile menu/modal
  Shows user name, role, department
  Quick links: My Profile, My Reports, Preferences
  
[⏻] Logout icon  
  Click → logout confirmation
  Clears session and redirects to login
```

## 5. Integration Icons (Center)

```
Total 7 integration icons, each with its own screen:

┌────┬─────────────────────┬──────────────────────────┐
│ ☁  │ OneDrive            │ /integrations/onedrive   │
├────┼─────────────────────┼──────────────────────────┤
│ 📁 │ SharePoint          │ /integrations/sharepoint │
├────┼─────────────────────┼──────────────────────────┤
│ 📦 │ ownCloud            │ /integrations/owncloud   │
├────┼─────────────────────┼──────────────────────────┤
│ 💬 │ Slack               │ /integrations/slack      │
├────┼─────────────────────┼──────────────────────────┤
│ 📧 │ Email (Outlook)     │ /integrations/email      │
├────┼─────────────────────┼──────────────────────────┤
│ 📱 │ WhatsApp Business   │ /integrations/whatsapp   │
├────┼─────────────────────┼──────────────────────────┤
│ 🔵 │ Google Apps         │ /integrations/google     │
└────┴─────────────────────┴──────────────────────────┘
```

### 5.1 Icon Specifications

```
Icon size: 24x24px (visual)
Touch target: 40x40px
Container: circular
Background: rgba(255,255,255,0.08) blur(16px)
Border: 1px solid rgba(255,255,255,0.12)
Spacing between icons: 8px

States:
  Default: subtle glass
  Hover: brighter glass, tooltip appears
  Connected: small green dot top-right
  Not connected: small gray dot
  Error/Disconnected: small red dot
  Notification: small badge with count

Hover tooltip (no animation, instant show):
  "OneDrive" + status (Connected / Not connected)
```

### 5.2 Each Integration Has Its Own Screen

```
Each icon → opens dedicated screen at /integrations/<service>

For now, each integration screen shows under-development template
with feature list and feedback form. Sets expectations and lets
you build incrementally.
```

### 5.3 Per-Integration Roadmap

```
☁ OneDrive:
  Phase 1: OAuth connection
  Phase 2: File browse/upload
  Phase 3: AI search across files
  Phase 4: Auto-save reports
  
📁 SharePoint:
  Phase 1: OAuth connection
  Phase 2: Browse company libraries
  Phase 3: Document AI Q&A
  Phase 4: Smart tagging
  
📦 ownCloud:
  Phase 1: Server URL + credentials
  Phase 2: Browse files
  Phase 3: Upload/download
  Phase 4: AI integration
  
💬 Slack:
  Phase 1: Workspace OAuth
  Phase 2: Send AI insights to channels
  Phase 3: Daily report bot
  Phase 4: Slash commands /ooa pnl
  
📧 Email (Outlook):
  Phase 1: OAuth (already in splash plan)
  Phase 2: Email digest
  Phase 3: Invoice tracking
  Phase 4: Smart replies
  
📱 WhatsApp Business:
  Phase 1: Business API setup
  Phase 2: Daily report delivery
  Phase 3: Query via WhatsApp
  Phase 4: Voice notes in WhatsApp
  
🔵 Google Apps:
  Phase 1: Google OAuth
  Phase 2: Drive integration
  Phase 3: Sheets data sync
  Phase 4: Calendar integration
```

## 6. Utility Icons (Right)

```
[🔍] Global Search
  Click → command palette opens (Cmd+K style)
  Search across: chats, reports, projects, settings

[🔔] Notifications
  Badge with unread count
  Click → notifications panel slides out from right
  Shows: alerts, scheduled reports ready, mentions

[⚙] Settings
  Click → settings page
  Theme, language, integrations, account, etc.

[⏻] Logout
  Click → confirm logout
```

---

# PART III — LEFT SIDEBAR (Quick Actions)

## 7. Always-Visible Quick Actions

```
Position: Fixed left
Width: 80px (collapsed icons only) OR 240px (expanded with labels)
Toggle: Click logo at top OR keyboard shortcut

Items (stacked vertically):
┌──────────────┐
│   ◊ OOA      │ ← Logo, click to expand/collapse
├──────────────┤
│   📊 P&L     │
│   🏗️ Proj    │
│   💰 Cash    │
│   📈 Reports │
│   🎤 Voice   │
│   📋 Tasks   │
│   🔍 Search  │
├──────────────┤
│   ↺ History  │ ← Recent chats
│   ⭐ Pinned  │ ← Pinned chats
└──────────────┘

Each item:
  Icon: 24x24px
  Label: 13px (only when expanded)
  Hover: background change
  Click: opens chat with pre-filled query
```

## 8. Quick Action Behavior

```
Click "📊 P&L":
  → If chat empty: opens with query "Show me P&L this month"
  → If chat has history: appends new query, keeps history
  → No clarification needed for quick actions (uses defaults)

Quick action vs typing:
  Typing: requires user input, may trigger clarifications
  Quick action: pre-configured, instant action
```

---

# PART IV — MAIN CHAT VIEW

## 9. Scrolling Chat Behavior (Like Claude/ChatGPT)

```
Layout:
  ┌────────────────────────────────────┐
  │  ▲ Older messages above            │
  │                                    │
  │  ─── Today ───                     │
  │                                    │
  │  [User] Show me P&L                │
  │                                    │
  │  [AI] Here's your P&L:             │
  │      [KPI cards]                   │
  │      [Chart]                       │
  │      [Suggestions]                 │
  │                                    │
  │  [User] Compare with last month    │
  │                                    │
  │  [AI] Comparison shows...          │
  │      [Comparative table]           │
  │                                    │
  │  ▼ Latest message                  │
  │                                    │
  │  ─────────────────────────────────│
  │  [Type or speak...] [🎤] [→]      │ ← Input at bottom
  │  ─────────────────────────────────│
  └────────────────────────────────────┘

Scrolling behavior:
  ✦ Auto-scroll to bottom on new message
  ✦ User can scroll up to view history
  ✦ If user scrolled up, NEW MESSAGE INDICATOR appears
    "↓ New response below" pill at bottom
  ✦ Smooth scroll on new message ONLY (this is the one motion exception)
  ✦ Date separators: "Today", "Yesterday", "May 12", etc.
  ✦ Lazy load older messages on scroll up
```

## 10. Click-Anywhere-to-Type Feature

```
Feature: Press any key anywhere → input becomes focused

Implementation:
  - Global keyboard listener
  - If keypress is not in another input
  - And not a system shortcut (Cmd+_, Ctrl+_, etc.)
  - And not modifier-only keys
  - Then: focus input, append the character

Exceptions:
  - Escape: clears input or closes panels
  - Arrow keys: scroll chat
  - Cmd/Ctrl+_: system shortcuts
  - Function keys: ignored
  - Tab: navigation
  
User experience:
  User is reading a long response
  Types "show me top customers"
  Input box automatically focuses and captures the keys
  No need to click input first

Code pattern:
  document.addEventListener('keydown', (e) => {
    // Skip if modifier keys
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    
    // Skip if already in input/textarea
    if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;
    
    // Skip special keys
    if (e.key.length !== 1 && e.key !== 'Backspace') return;
    
    // Focus the chat input
    const input = document.querySelector('#chat-input');
    if (input) {
      input.focus();
    }
  });
```

## 11. Message Layout

```
USER MESSAGE (right-aligned):
  ┌────────────────────────────────────┐
  │                       [Avatar]     │
  │  ┌─────────────────────────────┐   │
  │  │ Show me P&L this month       │   │
  │  └─────────────────────────────┘   │
  │  10:42 AM                          │
  └────────────────────────────────────┘

AI MESSAGE (left-aligned):
  ┌────────────────────────────────────┐
  │ [Avatar]                           │
  │  ┌─────────────────────────────┐   │
  │  │ Here's your P&L for April:   │   │
  │  │                              │   │
  │  │ Income: AED 17.4M           │   │
  │  │ ...                          │   │
  │  └─────────────────────────────┘   │
  │                                    │
  │  [Visualization cards]             │
  │  [KPI Card] [Chart]                │
  │                                    │
  │  [💡] [💡] [💡] Suggestions        │
  │                                    │
  │  10:42 AM | [Drag to Visualize ⤴]│ ← Action hint
  └────────────────────────────────────┘
```

## 12. Input Bar Design

```
Position: Fixed bottom of chat column
Width: 100% of chat column
Padding: 16px

┌────────────────────────────────────────┐
│ ┌──────────────────────────────────┐   │
│ │ Type or speak...        [🎤][→] │   │
│ └──────────────────────────────────┘   │
│  Hint: Press any key to start typing  │
└────────────────────────────────────────┘

Specifications:
  Container: glass white, rounded 16px
  Padding: 12px 16px
  Background: rgba(255,255,255,0.6) blur(24px)
  Border: 1px solid rgba(255,255,255,0.8)
  Min height: 48px
  Max height: 200px (grows with content)
  Font: 15px, weight 400

Mic button (🎤):
  Circular 36x36
  Hold to record
  Background gold when recording (no animation, just color change)

Send button (→):
  Circular 36x36
  Disabled when input empty
  Active: gold gradient background
  Click: send message instantly
```

---

# PART V — VISUALIZE PANEL

## 13. Auto Show/Hide Behavior

```
DEFAULT STATE: HIDDEN
  Panel collapsed to thin strip on right edge
  Just shows vertical text "VISUALIZE" with ◊ icon
  Width: 40px

AUTO-SHOW TRIGGERS:
  1. User generates report/visualization → panel slides in
  2. User says "visualize this" or similar → panel opens
  3. User drags any message → panel auto-opens (already planned)
  4. User clicks the collapsed strip → manual open

AUTO-HIDE TRIGGERS:
  1. User clicks X on panel
  2. User completes export (PDF downloaded)
  3. After 30 seconds of inactivity (configurable)
  4. User asks new unrelated question

MANUAL CONTROL:
  - Toggle button (collapsed strip on right edge)
  - Keyboard shortcut: Cmd+V or Cmd+Shift+V
  - Setting: "Auto-show Visualize panel" toggle
```

## 14. Visualize Panel — Siri-Style Border Animation

```
KEY DESIGN ELEMENT: The Siri-style colored border around the panel

When Visualize Agent is ACTIVE (working/thinking):
  Panel has animated colorful border like Siri's wave
  
Inactive (waiting for user):
  Panel has subtle static border (no animation)
  
Active states:
  - User dropped something → border pulses gold
  - Agent processing → border has rainbow gradient flowing
  - Generating PDF → border has progress wave
  - Complete → border settles to solid gold
```

### 14.1 The Siri-Style Animation (THE ONLY MOTION ALLOWED)

```css
/* This IS the exception to "no motion" rule */
/* It's a signature feature, like Siri's listening orb */

.visualize-panel {
  position: relative;
  overflow: hidden;
  border-radius: 24px;
}

.visualize-panel::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 26px;
  padding: 2px;
  background: conic-gradient(
    from var(--rotation),
    #c9a84c,      /* gold */
    #4ecdc4,      /* cyan */
    #8b5cf6,      /* purple */
    #ff6b6b,      /* coral */
    #c9a84c       /* gold (close loop) */
  );
  -webkit-mask: 
    linear-gradient(#fff 0 0) content-box, 
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  animation: rotateBorder 8s linear infinite;
}

@property --rotation {
  syntax: '<angle>';
  initial-value: 0deg;
  inherits: false;
}

@keyframes rotateBorder {
  to { --rotation: 360deg; }
}

/* Inactive: slower, subtle */
.visualize-panel.inactive::before {
  animation-duration: 16s;
  opacity: 0.5;
}

/* Active: faster, brighter */
.visualize-panel.active::before {
  animation-duration: 4s;
  opacity: 1;
  filter: brightness(1.3) saturate(1.5);
}

/* Processing: even faster + pulse */
.visualize-panel.processing::before {
  animation-duration: 2s;
  filter: brightness(1.5);
}
```

### 14.2 Inside Panel Animations

```
INSIDE the Visualize panel, allowed animations:

1. AGENT THINKING INDICATOR
   When Visualize agent is processing:
   
   ┌──────────────────┐
   │ ◊ Visualize      │
   │                  │
   │  ●───●───●       │  ← orbs gently pulse
   │                  │
   │  Designing...    │
   │                  │
   └──────────────────┘
   
   Three orbs in a row, gentle scale animation

2. DROP ZONE PULSE
   When item is being dragged over:
   Drop zone border pulses with gold
   Subtle, not distracting
   Stops when item dropped

3. GENERATION PROGRESS
   When PDF/Excel generating:
   
   ┌──────────────────┐
   │ Generating PDF   │
   │ ▓▓▓▓░░░░░░ 40%  │  ← progress bar
   │                  │
   │ • Cover ✓        │
   │ • KPIs ✓         │
   │ • Charts ⟳       │  ← spinning
   │ • Tables ◯       │
   │ • Insights ◯     │
   └──────────────────┘

4. PREVIEW MATERIALIZE
   When preview loads:
   Fade in over 0.3s
   Subtle scale from 0.95 to 1.0
   
5. SUCCESS CELEBRATION
   When report ready:
   Quick gold sparkle (1 second)
   Then static
   "✓ Ready" badge
```

## 15. Panel Internal Layout

```
┌────────────────────────────────────┐
│  ◊ Visualize         [_][X]        │ ← header
├────────────────────────────────────┤
│                                    │
│  ┌──────────────────────────────┐  │
│  │  Drop response here          │  │ ← drop zone
│  │                              │  │
│  │  Or current items shown      │  │
│  └──────────────────────────────┘  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │  Agent chat                  │  │
│  │  ◊ What format?              │  │
│  │  [PDF][Excel][Dashboard]     │  │
│  │                              │  │
│  │  ...                         │  │
│  └──────────────────────────────┘  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │  Live preview                │  │
│  │  [Thumbnail]                 │  │
│  └──────────────────────────────┘  │
│                                    │
│  [Download] [Email] [Share]        │
│                                    │
└────────────────────────────────────┘

Width: 380px when expanded
Height: 100vh - top bar
Position: Fixed right
Z-index: above chat
```

## 16. Auto-Show Detection Logic

```python
# Backend: Detect when to suggest opening Visualize
def should_auto_show_visualize(ai_response):
    """
    Return true if response contains visualization-worthy content.
    """
    if ai_response.get("visualization"):
        return True
    
    keywords = [
        "report", "chart", "visualize", "graph",
        "pdf", "excel", "export", "download"
    ]
    text = ai_response.get("text", "").lower()
    return any(kw in text for kw in keywords)


# Add flag to response
response = {
    "text": "...",
    "visualization": {...},
    "auto_show_visualize": True,  # ← Frontend reads this
}


# Frontend handler
if (response.auto_show_visualize) {
    setVisualizePanelOpen(true);
    setVisualizeContext({
        droppedItems: [response],
    });
}
```

---

# PART VI — INTEGRATION SCREENS

## 17. Standard Template for All Integration Screens

```
┌────────────────────────────────────────────────────────┐
│ ← Back to Chat                            [⚙ Settings]│
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │              [Large icon, 80x80]                 │ │
│  │              Service Name                        │ │
│  │              (e.g., OneDrive Integration)        │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │  🚧 Under Development                            │ │
│  │                                                  │ │
│  │  This integration is being built.                │ │
│  │  Estimated release: Q2 2026                      │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  What's Coming:                                       │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │ ✦ Feature 1                                      │ │
│  │   Brief description                              │ │
│  ├──────────────────────────────────────────────────┤ │
│  │ ✦ Feature 2                                      │ │
│  │   Brief description                              │ │
│  ├──────────────────────────────────────────────────┤ │
│  │ ✦ Feature 3                                      │ │
│  │   Brief description                              │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  [ Get Notified When Ready ]                          │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │  💬 Feedback                                     │ │
│  │  What would you like this integration to do?    │ │
│  │  ┌──────────────────────────────────────────┐    │ │
│  │  │                                          │    │ │
│  │  └──────────────────────────────────────────┘    │ │
│  │  [Submit Feedback]                              │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
└────────────────────────────────────────────────────────┘
```

## 18. Per-Integration Content Summary

```
☁ OneDrive: AI file search, doc Q&A, auto-save reports
📁 SharePoint: Browse libraries, doc intelligence, permissions aware
📦 ownCloud: Self-hosted connection, secure private storage
💬 Slack: Insights bot, slash commands, mention to ask
📧 Email (Outlook): Digest, meeting prep, invoice tracking
📱 WhatsApp: Query via chat, daily summary, voice notes
🔵 Google Apps: Drive, Sheets, Calendar, Gmail integration
```

---

# PART VII — STYLES & VISUAL SYSTEM

## 19. Complete CSS Variables

```css
:root {
  /* Backgrounds */
  --bg-base: rgba(250, 247, 240, 1);
  --bg-glass: rgba(255, 255, 255, 0.6);
  --bg-glass-hover: rgba(255, 255, 255, 0.75);
  
  /* Borders */
  --border-glass: rgba(255, 255, 255, 0.8);
  --border-subtle: rgba(0, 0, 0, 0.06);
  --border-focus: rgba(201, 168, 76, 0.5);
  
  /* Text */
  --text-primary: #1a2744;
  --text-secondary: #5a6378;
  --text-muted: rgba(26, 39, 68, 0.5);
  
  /* Accents */
  --accent-gold: #c9a84c;
  --accent-gold-dark: #a8873d;
  --accent-cyan: #4ecdc4;
  --accent-coral: #ff6b6b;
  --accent-purple: #8b5cf6;
  
  /* Glass effects */
  --blur-light: blur(16px);
  --blur-medium: blur(24px);
  --blur-heavy: blur(40px);
  
  /* Border radius */
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;
  --radius-2xl: 24px;
  --radius-pill: 100px;
}

/* Dark theme */
[data-theme="dark"] {
  --bg-base: #0a0f1e;
  --bg-glass: rgba(255, 255, 255, 0.06);
  --border-glass: rgba(255, 255, 255, 0.1);
  --text-primary: #e8eaf6;
}
```

## 20. Animation Policy (Strict)

```
ALLOWED MOTION:
  ✓ Visualize panel Siri-style border (signature feature)
  ✓ Visualize panel internal: agent thinking, generation progress
  ✓ Smooth scroll on new message (chat auto-scroll)
  ✓ Hover state: background color change only (0.15s)
  ✓ Focus state: border color change only (0.15s)
  ✓ Panel slide in/out: 0.2s ease
  ✓ Loading spinner: simple rotation (Visualize generation)

FORBIDDEN MOTION:
  ✗ Animated gradients on backgrounds
  ✗ Floating particles
  ✗ Bob/float animations
  ✗ Parallax effects
  ✗ Twinkling stars
  ✗ Auto-rotating content
  ✗ Decorative animations
  ✗ Bounce effects
```

---

# PART VIII — RESPONSIVE BEHAVIOR

## 21. Desktop (> 1200px)

```
Full 3-column layout
Visualize panel at 380px
Quick actions sidebar at 80px (collapsed) or 240px (expanded)
Chat takes remaining space
```

## 22. Tablet (768-1200px)

```
Quick actions: collapses to icons only (80px)
Visualize panel: overlays on top of chat (slides in)
Chat: takes full width when Visualize hidden
```

## 23. Mobile (< 768px)

```
Quick actions: bottom sheet drawer
Visualize panel: full-screen overlay
Top bar: compact, integration icons in menu
Chat: full screen
Integration icons: accessible via menu button
```

---

# PART IX — IMPLEMENTATION PHASES

## 24. Build Order (6 Weeks)

### Phase 1 — Top Bar Redesign (Week 1)
```
[ ] Build new top bar layout
[ ] Add profile + logout icons (left)
[ ] Add 7 integration icons (center) with status dots
[ ] Add utility icons (right)
[ ] Implement tooltips on hover
[ ] Test on different screen sizes
```

### Phase 2 — Integration Screens (Week 2)
```
[ ] Create routing for /integrations/<service>
[ ] Build "Under Development" template
[ ] Per-integration content (7 screens)
[ ] Feedback form
[ ] "Get Notified" subscription
```

### Phase 3 — Left Sidebar (Week 2)
```
[ ] Build quick actions sidebar
[ ] Expand/collapse functionality
[ ] Quick action click → pre-fill chat
[ ] History section (recent chats)
[ ] Pinned section
```

### Phase 4 — Chat View Redesign (Week 3)
```
[ ] Implement scrolling chat layout
[ ] Auto-scroll on new message
[ ] "New message" indicator when scrolled up
[ ] Date separators
[ ] Click-anywhere-to-type feature
[ ] Lazy load older messages
```

### Phase 5 — Visualize Panel (Week 4)
```
[ ] Build panel layout (380px right side)
[ ] Implement Siri-style border animation
[ ] Auto show/hide logic
[ ] Internal animations (thinking, progress)
[ ] Drop zone (already planned)
[ ] Wire up to Visualize agent backend
```

### Phase 6 — Polish & Integration (Week 5-6)
```
[ ] Apply complete style system
[ ] Test light/dark themes
[ ] Test Arabic RTL
[ ] Mobile responsive layout
[ ] Accessibility audit
[ ] Performance optimization
[ ] User testing
```

---

# PART X — TELL CURSOR

```
"Read MAIN_SCREENS_LAYOUT_PLAN.md.

This is the main app interface redesign.

Start Phase 1: Top Bar.

Build new top bar with:
- Left: profile + logout icons
- Center: 7 integration icons (☁ 📁 📦 💬 📧 📱 🔵)
- Right: search, notifications, settings, logout

Each integration icon → routes to /integrations/<service>

For now all integration screens show 'Under Development' template
with feature list and feedback form.

Critical:
- Clean white contrast glassy design (from SPLASH_SCREEN_PLAN.md)
- NO motion animations EXCEPT:
  - Visualize panel Siri-style border (signature)
  - Smooth chat scroll on new message
  - Hover state background changes (0.15s)
- All other UI must be STATIC

Reference:
- SPLASH_SCREEN_PLAN.md for design language
- VISUALIZE_AGENT_PLAN.md for Visualize panel logic
- PROJECT_CONTEXT.md for code patterns

After Phase 1, proceed through phases sequentially."
```

---

## Summary of What's New

```
✦ Top bar with 7 integration icons (each with own screen)
✦ Profile + logout icons (clear identity area)
✦ Left sidebar with quick actions (always visible)
✦ Scrolling chat view (like Claude/ChatGPT)
✦ Click-anywhere-to-type feature
✦ Auto show/hide Visualize panel
✦ Siri-style colored border on Visualize panel
✦ Internal animations inside Visualize only
✦ Per-integration "Under Development" screens
✦ Strict no-motion policy everywhere else
✦ Roadmap for each integration
```

The Visualize panel will feel ALIVE while everything else stays CLEAN and STATIC. Best of both worlds — premium static design with one signature animated element.
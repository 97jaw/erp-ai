# UI Plan v1.1 — Odoo Omni-Agent

> **Vision:** A cinematic, glassy AI assistant that feels alive — premium UAE corporate aesthetic with bilingual Arabic/English support, dual themes, ambient animations, and audio feedback.

---

## 1. Design Philosophy

```
✦ Glassmorphism with depth
✦ Animated gradient backgrounds (subtle, breathing motion)
✦ Particle and light effects
✦ Audio feedback for every meaningful action
✦ Smooth 60fps transitions everywhere
✦ Premium corporate feel — Bloomberg meets Apple
✦ Voice-first interactions with visual companions
```

---

## 2. Theme System

### 2.1 Theme Names & Identity

```
🌟 STARLIGHT  — Light theme, daytime, elegant
🦇 BLACKBAT   — Dark theme, premium, focused
```

Toggle position: Top-right corner with animated sun/moon transition icon (3D flip animation).

### 2.2 STARLIGHT Theme Specifications

```
Background Base:
  Linear gradient → from #f4f7fc → #e8edf7 → #f0e7f9
  Animated: 20s loop, subtle hue shift between cream/lavender/peach

Glass Surfaces:
  rgba(255, 255, 255, 0.55) backdrop-filter: blur(24px)
  Border: rgba(255, 255, 255, 0.65)
  Shadow: 0 8px 32px rgba(31, 38, 135, 0.12)
  Inner glow: inset 0 1px 0 rgba(255,255,255,0.8)

Accents:
  Primary Gold:    #c9a84c (UAE corporate)
  Secondary Cyan:  #4ecdc4 (success/positive)
  Alert Coral:     #ff6b6b (error/negative)
  Royal Blue:      #5b6fe6 (info)

Text:
  Primary:   #1a1f3a (deep navy)
  Secondary: #5a6378
  Muted:     rgba(26, 31, 58, 0.4)

Glow Effects:
  Soft golden orbs floating in background
  3 layers of gradient mesh moving slowly
```

### 2.3 BLACKBAT Theme Specifications

```
Background Base:
  Radial gradient → #060b1a center → #0a0f1e → #050714 edges
  Animated: 20s loop, subtle nebula motion
  Stars: 100 tiny twinkling dots (animated opacity)

Glass Surfaces:
  rgba(255, 255, 255, 0.05) backdrop-filter: blur(20px) saturate(180%)
  Border: rgba(255, 255, 255, 0.08)
  Shadow: 0 8px 32px rgba(0, 0, 0, 0.5)
  Inner glow: inset 0 1px 0 rgba(255,255,255,0.1)

Accents:
  Primary Gold:    #d4af37 (luxe gold)
  Neon Cyan:       #4ecdc4 with bloom glow
  Coral Red:       #ff6b6b with neon edge
  Royal Purple:    #8b5cf6 (info)

Text:
  Primary:   #e8eaf6
  Secondary: rgba(232, 234, 246, 0.7)
  Muted:     rgba(232, 234, 246, 0.4)

Glow Effects:
  Aurora-like color washes (purple/teal/gold)
  Pulsing radial glows behind components
  Subtle starfield with parallax
```

### 2.4 Theme Transition

```
Trigger: Click theme toggle button
Animation:
  1. Toggle icon rotates 180° (Y-axis flip) over 600ms
  2. Background morphs via cross-fade (800ms ease-in-out)
  3. Glass surfaces slide opacity (400ms)
  4. Subtle ambient sound: soft chime (different per theme)
  5. Particles burst from toggle button (Framer Motion)

Persisted: localStorage('ooa_theme')
Default: BLACKBAT (matches system dark mode preference)
```

---

## 3. Background Animation System

### 3.1 Layer Composition

```
Layer 0 (deepest): Static gradient base
Layer 1:           Animated mesh gradient (CSS keyframes, 30s loop)
Layer 2:           Floating orbs (3-5, large blurred circles)
                   - Move slowly in random paths
                   - Color cycles between accent colors
                   - Opacity pulses 0.3 ↔ 0.6
Layer 3:           Particles
                   - STARLIGHT: floating dust motes (white)
                   - BLACKBAT:  twinkling stars + occasional shooting stars
Layer 4 (top):     Vignette overlay (subtle darkening at edges)
```

### 3.2 Animation Specifications

```css
@keyframes meshFlow {
  0%   { transform: translate(0, 0) rotate(0deg); }
  33%  { transform: translate(-3%, 2%) rotate(120deg); }
  66%  { transform: translate(2%, -3%) rotate(240deg); }
  100% { transform: translate(0, 0) rotate(360deg); }
}

@keyframes orbFloat {
  0%, 100% { transform: translate(0, 0) scale(1); }
  25%      { transform: translate(40px, -30px) scale(1.05); }
  50%      { transform: translate(-20px, 40px) scale(0.95); }
  75%      { transform: translate(-50px, -10px) scale(1.02); }
}

@keyframes twinkle {
  0%, 100% { opacity: 0.2; }
  50%      { opacity: 1; }
}
```

### 3.3 Performance Considerations

```
- Use transform and opacity ONLY (GPU-accelerated)
- Will-change: transform on orbs
- Reduce particle count on mobile (50 → 20)
- Disable on prefers-reduced-motion
- Pause when tab not visible (Page Visibility API)
```

---

## 4. Glassmorphism Component Library

### 4.1 GlassCard

```
Base:
  background: theme.glass.bg
  backdrop-filter: blur(24px) saturate(180%)
  border: 1px solid theme.glass.border
  border-radius: 20px
  box-shadow: theme.glass.shadow
  position: relative
  overflow: hidden

Hover state:
  transform: translateY(-2px)
  box-shadow: 0 12px 40px rgba(...)
  transition: 300ms ease

Variant: Premium (with gradient border)
  border-image: linear-gradient(135deg, gold, transparent, gold) 1
  Inner shimmer animation
```

### 4.2 GlassButton

```
Primary:
  background: gradient (gold tones)
  glow on hover
  ripple effect on click
  haptic-like scale (0.96) on tap

Secondary:
  glass + border
  subtle glow on hover

Icon Button:
  circular glass
  rotates on hover
  glow trail on click
```

### 4.3 GlassInput

```
Default state:
  Transparent glass with thin border
  Animated focus ring (gradient sweep around border)

Focused state:
  Border becomes gradient gold→cyan
  Subtle glow underneath
  Label floats up with smooth transition

With voice indicator:
  Live waveform animation when recording
  Pulsing red dot on the right
```

---

## 5. Authentication Screen (Login)

### 5.1 Layout Composition

```
┌────────────────────────────────────────────┐
│         [Theme Toggle] (top-right)         │
│                                            │
│           [Animated Logo]                  │
│         "Odoo Omni-Agent"                  │
│        "Welcome to Elrace AI"              │
│                                            │
│      ┌────────────────────────────┐       │
│      │  ◈  Enter your File ID     │       │
│      │  [_______________]    →    │       │
│      └────────────────────────────┘       │
│                                            │
│         "Powered by Claude AI"             │
│              "Elrace 2026"                 │
└────────────────────────────────────────────┘
```

### 5.2 Login Element Animations

**Logo (Cinematic Intro)**
```
On page load:
  1. Logo icon (◈) appears at center, small (0%)
  2. Scales to 100% over 800ms with ease-out-back
  3. Rotates 360° during scale-up
  4. Golden glow pulses outward (ripple) 3x
  5. Logo text fades up from below (200ms delay)
  6. Subtitle fades in (400ms delay)
  7. Login card slides up from below (600ms delay)
```

**File ID Input Card**
```
Visual:
  Glassy card with gradient border
  Premium animated border (rotating gradient)
  Floating placeholder that animates to top on focus
  Right-side arrow button (gold) — pulses subtly

Idle state:
  Placeholder: "Enter your Elrace File ID"
  Soft glow underneath
  Suggestion: "e.g., ELR-2026-001"

Typing state:
  Each character bounces in slightly
  Character counter appears bottom-right
  Auto-validates format (regex pattern)
  Green checkmark when valid format

Submit:
  Click → button scales down
  Card morphs into loading state
```

**Loading / Authentication State**
```
Card transforms:
  Input fades out (200ms)
  Spinner appears at center
  Spinner type: 3D rotating ring with gradient
  Below spinner: animated text rotation:
    "Connecting to Odoo..."
    "Verifying your credentials..."
    "Loading your workspace..."
  Each text fades through ease 800ms

Background:
  Slows down animation slightly
  Subtle pulse synced with spinner
```

**Success State**
```
Animation sequence (1.5s total):
  1. Spinner morphs into a glowing checkmark
  2. Burst of golden particles outward
  3. Audio plays:
     - Arabic: "أهلاً بك" (Welcome) — male voice, warm
     - English: "Welcome to your workspace"
  4. Card scales up + fades
  5. Background transitions:
     - More vibrant
     - Adds chat-room ambient particles
  6. Chat screen slides in from right
```

**Failure State**
```
Animation sequence:
  1. Card shakes horizontally (3 oscillations)
  2. Border flashes red
  3. Error icon appears with bounce
  4. Audio plays:
     - Arabic: "عذراً، رقم الملف غير صحيح" (Sorry, invalid file ID)
     - English: "Sorry, that File ID was not recognized"
  5. Input clears with smooth fade
  6. Returns to idle state after 2s
  7. Subtle red glow lingers
```

### 5.3 Audio Feedback System

```
File location: /public/sounds/
Files needed:
  - login-success-ar.mp3  (Arabic welcome)
  - login-success-en.mp3  (English welcome)
  - login-fail-ar.mp3     (Arabic error)
  - login-fail-en.mp3     (English error)
  - chime-success.mp3     (UI confirmation)
  - chime-error.mp3       (UI warning)
  - theme-toggle.mp3      (Theme switch sound)
  - message-send.mp3      (Send sound)
  - message-receive.mp3   (Response arrival)
  - typing-start.mp3      (AI thinking sound — subtle)

Voice Generation:
  Use ElevenLabs API to generate Arabic voice files
  Same voice as TTS for consistency
  Or use existing TTS endpoint with cached blobs
```

### 5.4 Backend Integration

```
Endpoint: POST /auth/login
Payload: { file_id: "ELR-2026-001" }

Backend logic:
  1. Validate format (regex)
  2. Call Odoo search_read on res.users
     OR custom user lookup method
  3. If match: generate session token, return user info
  4. If no match: return 401

Response:
  Success:
    {
      "status": "success",
      "session_id": "uuid",
      "user_name": "Ahmed Al-Maktoum",
      "language": "ar",
      "audio_response": "/sounds/login-success-ar.mp3"
    }
  Failure:
    {
      "status": "error",
      "message": "File ID not found",
      "audio_response": "/sounds/login-fail-ar.mp3"
    }
```

---

## 6. Post-Login Transition

### 6.1 Choreographed Sequence (2 seconds)

```
T+0.0s: Success checkmark + audio plays
T+0.3s: Background gradient shifts (more vibrant)
T+0.4s: Login card scales up 1.2x and fades
T+0.6s: Chat screen elements slide in (staggered):
        - Header (from top, 200ms)
        - Sidebar/Quick actions (from left, 300ms delay)
        - Main chat area (from right, 400ms delay)
        - Input bar (from bottom, 500ms delay)
T+1.5s: Welcome message appears in chat:
        - Bot avatar fades in
        - Greeting types out character by character (Claude-style)
        - Audio: subtle chime as each suggestion chip appears
T+2.0s: Ready state
```

---

## 7. Main Chat Screen

### 7.1 Layout

```
┌──────────────────────────────────────────────────────┐
│ [Logo] Odoo Omni-Agent           [🌟][Profile][Logout]│
├──────────┬───────────────────────────────────────────┤
│          │                                           │
│ Quick    │      💬 Chat Area                        │
│ Actions  │                                           │
│          │  [Bot Avatar] Welcome message...         │
│ 📊 P&L   │                                           │
│ 🏗️ Proj  │  [💡] [💡] [💡] [💡] Suggestions         │
│ 👥 Part. │                                           │
│ 📈 Trial │  [User Msg] →                            │
│ 🌐 Lang  │                                           │
│          │  ← [Bot Msg with Visualization]          │
│ History  │                                           │
│ ────     │                                           │
│ Today    │                                           │
│ • P&L    │                                           │
│ • Cost   │                                           │
│          │                                           │
├──────────┴───────────────────────────────────────────┤
│  [🎤] Type message... اكتب رسالتك...   [→]          │
└──────────────────────────────────────────────────────┘
```

### 7.2 Quick Action Cards (Sidebar)

```
Style:
  Each: Glass card with icon, label, subtle gradient on hover
  Icons: Lottie or animated SVG
  Hover: lifts 2px, glow intensifies
  Click: pulses + sends pre-defined query

Cards:
  📊 P&L Report      → "Show profit and loss this month"
  🏗️ Projects        → "Show active projects"
  👥 Receivables     → "Who owes us money"
  📈 Trial Balance   → "Show trial balance"
  💰 Expenses        → "Show this month expenses"
  📅 Compare         → "Compare this month vs last month"
```

### 7.3 Welcome Message Suggestion Cards

```
Layout: 2x2 grid of glassy cards
Each card: Icon + Title + Subtitle
Animation on appear: staggered fade-up

Examples:
  ┌─────────────────────┐  ┌─────────────────────┐
  │   📊 P&L Report     │  │   🏗️ Project Cost    │
  │  This month summary │  │  Specific project    │
  └─────────────────────┘  └─────────────────────┘
  ┌─────────────────────┐  ┌─────────────────────┐
  │   👥 Receivables    │  │   📅 Compare        │
  │  Who owes us money  │  │  Period comparison   │
  └─────────────────────┘  └─────────────────────┘

Hover: card lifts, icon animates (Lottie play)
Click: card flips, sends query, smoothly disappears
```

---

## 8. Message Bubble System

### 8.1 User Message

```
Alignment: Right (auto-flips RTL for Arabic)
Style:
  Gradient gold background (90deg, c9a84c → a8873d)
  Border-radius: 20px (top-left less rounded)
  Subtle gold glow
  Shadow

Animation on appear:
  Slide in from right + fade
  Slight bounce at end (spring physics)
```

### 8.2 Bot Message

```
Alignment: Left (auto-flips RTL for Arabic)
Style:
  Glass card with theme accent
  Border-radius: 20px (top-right less rounded)
  Avatar: 36px circular, animated gradient orb

Animation on appear:
  Avatar pops in (scale 0 → 1.1 → 1)
  Text streams character by character (matches Claude API stream)
  Each chunk has subtle glow as it arrives
  Cursor blinks at the end while streaming
```

### 8.3 AI Thinking Indicator

```
When: While waiting for first token after send
Visual:
  Bot avatar appears
  3 dots bouncing with stagger
  Soft golden glow pulses around avatar
  Audio: very subtle ambient "thinking" sound (loop)

When first token arrives:
  Dots fade out
  Text starts streaming
  Sound fades out
```

### 8.4 Visualization Reveal Animation

```
When viz appears below text:
  1. Glass container fades up (200ms delay after text complete)
  2. Inner elements stagger in:
     - Header label (100ms)
     - Big number / value (200ms with count-up animation)
     - Sub-details (300ms each)
     - Chart bars/lines draw themselves (500ms)
  3. Subtle particle effect upward from card
  4. Audio: gentle "ding" when complete
```

---

## 9. Visualization Components (Themed)

### 9.1 KPI Card

```
Layout:
  [Icon/Trend Arrow]
  [Label]
  [BIG NUMBER]   ← Count-up animation from 0
  [Unit]
  [Trend %] [vs last period]

Animation:
  Number counts up from 0 to value (800ms)
  Trend arrow animates direction
  Subtle pulse glow if value is significant
  Hover: lifts, glow intensifies

Themed colors:
  Positive: green/cyan glow
  Negative: coral/red glow
  Neutral: gold glow
```

### 9.2 Financial Report Card

```
Layout:
  Header: Report name + date range
  4-grid: Income, Expenses, Net Profit, Margin
  Each cell: animated counter
  Color-coded by sign

Animation:
  Cells appear one by one (staggered 100ms)
  Numbers count up
  Margin percentage rolls into place
  Background gradient subtly shifts based on profit/loss
```

### 9.3 Data Table

```
Style:
  Glass background
  Gold accent header
  Hover row: subtle highlight + scale 1.005
  Striped rows (very subtle)

Animation:
  Rows fade in from top, staggered 40ms
  Click row: expands inline with smooth height transition
  Numbers in cells have subtle count-up
```

### 9.4 Bar Chart

```
Library: Recharts or Chart.js
Style:
  Bars: gradient fill (gold to lighter gold)
  Axis: thin lines, muted color
  Grid: barely visible
  Tooltip: glass card on hover

Animation:
  Bars grow from 0 to value (800ms with ease-out)
  Staggered (50ms per bar)
  Hover: bar glows, value pops out above
```

### 9.5 Line Chart (Time Series)

```
Animation:
  Line draws itself left to right (1.2s)
  Area below fades in
  Dots pop in one by one
  Latest dot pulses
```

---

## 10. Input Bar (Bottom)

### 10.1 Composition

```
┌─────────────────────────────────────────────────┐
│ [🎤]  Ask anything in any language...   [→]    │
└─────────────────────────────────────────────────┘
  ↑                                          ↑
  Voice Input                            Send Button
```

### 10.2 Voice Recording State

```
On press-hold mic button:
  1. Mic icon transforms to live waveform
  2. Background glows red gently
  3. Live audio visualizer below input
  4. Timer appears (00:01, 00:02...)
  5. Background particles change behavior:
     - More active
     - Color shifts toward red

On release:
  1. Waveform freezes briefly
  2. "Sending audio..." appears
  3. Background returns to normal
  4. Transcript appears in input briefly before sending
```

### 10.3 Send Button States

```
Idle:    Static gold circle with arrow
Hover:   Glow intensifies, rotates 15°
Click:   Scales down + ripple effect
Sending: Arrow morphs into spinner
Sent:    Quick checkmark flash
```

### 10.4 Input Suggestions (Type-ahead)

```
As user types:
  Suggestion dropdown appears above input
  Glass card with up to 5 matches from history
  Arrow keys to navigate
  Tab/Enter to select
  Smooth height transitions
```

---

## 11. Suggestion Chips (After Each Bot Response)

```
Layout: Horizontal scroll, glass chips
Animation: Fade up staggered after viz appears

Each chip:
  Glass background
  Border: gradient gold (subtle)
  Icon (lightbulb emoji or sparkle)
  Text in user's language

Hover: chip glows, scales 1.03
Click: chip pulses, sends query, fades out
```

---

## 12. Theme Toggle Animation Detail

```
Position: Top-right
Component: Animated 3D toggle

States:
  Light (STARLIGHT): Sun icon, golden glow
  Dark (BLACKBAT):   Moon icon, silver glow

Click sequence:
  1. Icon flips 180° on Y-axis (600ms)
  2. Mid-flip: icon switches (sun ↔ moon)
  3. Background gradient cross-fades (800ms)
  4. All glass elements subtly re-tint
  5. Audio: soft chime
  6. localStorage updates
```

---

## 13. Audio System Architecture

### 13.1 Sound Categories

```
UI Feedback (instant, short):
  - Button clicks       (15ms snap)
  - Toggle switches     (50ms chime)
  - Success ticks       (200ms ding)
  - Error alerts        (300ms buzz)

Conversational (longer):
  - Welcome messages    (1-2s)
  - Bot thinking loop   (continuous, faded)
  - Response complete   (250ms gentle chime)

Voice (TTS via ElevenLabs):
  - All bot responses can be auto-spoken (user toggle)
```

### 13.2 Sound Settings

```
User controls (in profile menu):
  ☑ UI sound effects
  ☑ Voice responses (auto-play TTS)
  ☐ Background ambient
  Volume slider (0-100%)

Defaults:
  UI sounds: ON
  Auto-play TTS: OFF (only when user requests voice)
  Ambient: OFF
  Volume: 60%
```

### 13.3 Implementation

```javascript
// Sound manager singleton
class SoundManager {
  play(soundKey, options = {})  // Plays sound
  preload(keys)                 // Cache audio
  setVolume(0-1)
  mute()
  unmute()
}

// Usage:
sound.play('message-send', { volume: 0.4 })
sound.play('login-success-ar')
```

---

## 14. Responsive Behavior

```
Desktop (>1024px):
  Full layout with sidebar
  Animations at full quality

Tablet (768-1024px):
  Sidebar collapses to icon-only
  Reduced particle count

Mobile (<768px):
  Sidebar becomes bottom sheet (swipe up)
  Simplified animations
  Stack visualizations
  Larger touch targets (44px min)
  Voice button more prominent
```

---

## 15. Accessibility (a11y)

```
✓ All animations respect prefers-reduced-motion
✓ Keyboard navigation throughout
✓ ARIA labels on all interactive elements
✓ Focus rings visible (custom-styled)
✓ Color contrast: WCAG AA minimum
✓ Screen reader compatible
✓ Audio captions / transcripts for TTS
✓ Skip-to-content link
```

---

## 16. Tech Stack for Implementation

### 16.1 Core Libraries

```
React 18                  — Already in place
Framer Motion             — Component animations
GSAP (optional)           — Complex sequence choreography
Lottie React              — Icon animations
React Spring (alternative)— Physics-based animations
Recharts                  — Charts/visualizations
Howler.js                 — Audio management
react-icons               — Icon library (or Lucide)
clsx                      — Conditional className utility
```

### 16.2 Theme System

```
Implementation: React Context + CSS variables
File: src/theme/ThemeProvider.jsx

Theme structure:
  {
    name: 'blackbat',
    colors: { ... },
    glass: { ... },
    gradients: { ... },
    animations: { ... }
  }

Switching: CSS variables change → all components re-tint
```

### 16.3 File Structure

```
ooa-ui/
├── src/
│   ├── App.jsx
│   ├── theme/
│   │   ├── ThemeProvider.jsx
│   │   ├── themes.js
│   │   └── animations.js
│   ├── components/
│   │   ├── auth/
│   │   │   ├── LoginScreen.jsx
│   │   │   ├── FileIdInput.jsx
│   │   │   └── AuthSpinner.jsx
│   │   ├── chat/
│   │   │   ├── ChatScreen.jsx
│   │   │   ├── MessageBubble.jsx
│   │   │   ├── TypingIndicator.jsx
│   │   │   ├── SuggestionChip.jsx
│   │   │   └── InputBar.jsx
│   │   ├── visualization/
│   │   │   ├── KPICard.jsx
│   │   │   ├── FinancialReport.jsx
│   │   │   ├── DataTable.jsx
│   │   │   └── BarChart.jsx
│   │   ├── glass/
│   │   │   ├── GlassCard.jsx
│   │   │   ├── GlassButton.jsx
│   │   │   └── GlassInput.jsx
│   │   ├── background/
│   │   │   ├── AnimatedBackground.jsx
│   │   │   ├── ParticleField.jsx
│   │   │   └── GradientMesh.jsx
│   │   └── common/
│   │       ├── ThemeToggle.jsx
│   │       ├── Logo.jsx
│   │       └── SoundManager.js
│   ├── hooks/
│   │   ├── useTheme.js
│   │   ├── useSound.js
│   │   ├── useVoice.js
│   │   └── useStream.js
│   └── styles/
│       ├── global.css
│       └── animations.css
└── public/
    ├── sounds/         (all audio files)
    └── lottie/         (animation JSON files)
```

---

## 17. Implementation Phases

### Phase A — Foundation (Week 1)
```
1. Set up theme system (Context + CSS vars)
2. Build glass component library
3. Implement animated background
4. Add sound manager
5. Theme toggle working
```

### Phase B — Authentication (Week 2)
```
1. Build LoginScreen layout
2. File ID input with animations
3. Loading states + spinner
4. Backend /auth/login endpoint
5. Audio feedback integration
6. Success/failure transitions
```

### Phase C — Chat Experience (Week 3)
```
1. Chat screen layout
2. Message bubbles with streaming
3. Input bar with voice
4. Quick action sidebar
5. Suggestion chips
6. Welcome message choreography
```

### Phase D — Visualizations (Week 4)
```
1. KPI Card with count-up
2. Financial Report card
3. Data Table with animations
4. Bar Chart with Recharts
5. Theme-aware coloring
6. Reveal animations
```

### Phase E — Polish (Week 5)
```
1. Mobile responsiveness
2. Accessibility audit
3. Performance optimization
4. Sound effects integration
5. Browser testing
6. Production build
```

---

## 18. Success Metrics

```
Performance:
  - Initial load: < 3s
  - Theme toggle: < 1s
  - Login → Chat transition: < 2s
  - Frame rate: consistent 60fps

User Experience:
  - "Wow" factor on first view (user testing)
  - Suggestion chip click rate
  - Average session duration
  - Voice usage rate

Technical:
  - Lighthouse score > 90
  - Bundle size < 500KB initial
  - Animations smooth on mid-range devices
  - Zero layout shifts (CLS = 0)
```

---

## 19. Backend Changes Required for v1.1

```
New Endpoints:
  POST /auth/login          — File ID authentication
  POST /auth/logout         — Session termination
  GET  /sounds/:filename    — Serve cached audio files
  GET  /user/profile        — Return user info

Updates:
  /chat/stream              — Add user_id to context
  All endpoints             — Require session token

New Odoo Method:
  authenticate_by_file_id(file_id) → user record
```

---

## 20. Reference Inspirations

```
Visual:
  - Apple Vision Pro UI (glass + depth)
  - Linear app (smooth animations)
  - Vercel landing page (gradient mesh)
  - Anthropic Claude.ai (clean chat)

Animations:
  - Framer.com homepage
  - Stripe's transitions
  - Apple keynote presentations

Audio:
  - iOS notification sounds
  - Loop Earplugs ad sounds (premium feel)
  - macOS UI sounds
```

---

## Notes for Implementation

```
✓ Build mobile-first, enhance for desktop
✓ Test on real devices, not just Chrome desktop
✓ Use AbortController to cancel animations on unmount
✓ Preload critical sounds on app start
✓ Cache theme preference in localStorage
✓ Provide instant feedback for every interaction
✓ Never block the UI during async operations
✓ Always have a fallback for animation failures
✓ Performance > Animation richness (when conflict)
```

---

## Future v1.2 Considerations

```
- Particle interactions (cursor-following)
- 3D card flip on hover (depth)
- Voice waveform live during AI speech
- Drag-and-drop file uploads in chat
- Multi-tab chat sessions
- Collaborative cursors (multi-user)
- AR mode (mobile camera + AI overlay)
```

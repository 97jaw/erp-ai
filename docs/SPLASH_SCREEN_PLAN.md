# SPLASH SCREEN REDESIGN PLAN

> **Design Direction:** Clean, white-contrast, glassy panels, NO motion animations. Static, premium, professional. Inspired by the Base44-style reference (hero composition, floating widget cards, greeting-first approach) — adapted for executive ERP context.

> **Read first:** `PROJECT_CONTEXT.md`, `V1.2_UI_LAYOUT.md`

---

# PART I — DESIGN PHILOSOPHY

## 1. The Aesthetic

```
✦ CLEAN — Minimal clutter, generous whitespace
✦ WHITE CONTRAST — Light backgrounds with dark text
                    OR dark hero with white text
                    Always strong contrast for readability
✦ GLASSY — Frosted glass panels with subtle transparency
✦ STATIC — No motion animations, no autoplay
✦ PREMIUM — Executive feel, not playful
✦ PROFESSIONAL — Business context, UAE corporate
✦ HERO COMPOSITION — Large beautiful background with content overlay
```

## 2. What's Different From V1.1 Plan

```
V1.1 had:
  ❌ Animated gradient backgrounds
  ❌ Floating particle systems
  ❌ Twinkling stars
  ❌ Bob animations
  ❌ Aurora effects
  ❌ Multiple moving layers

V1.2 redesign (this plan):
  ✓ Static hero image (high quality landscape/UAE skyline)
  ✓ Glass panels with no animation
  ✓ Smooth hover states only (subtle)
  ✓ Quick transitions on user actions (button clicks)
  ✓ Page transitions only when navigating
  ✓ Premium photography over generated effects
```

## 3. Inspiration Adapted

```
Reference (Base44 style):
  - Hero landscape image (cloud, mountain, sunset)
  - Greeting overlay (Good Evening Eleanor)
  - Category pills (Meditation, Sleep, Anti Stress)
  - Engagement widgets on right (likes, comments)
  - Tool cards bottom-right
  - Profile picture top-left
  - Search and notifications top-right

Our adaptation:
  - Hero: UAE skyline / Dubai/Abu Dhabi cityscape OR abstract glass texture
  - Greeting: "Good Evening Ahmed" with role/department
  - Quick action pills (P&L, Projects, Reports, Voice)
  - Right widgets: Today's stats, Recent reports, AI insights
  - Bottom right: Outlook integration card OR Feature showcase
  - Profile: User avatar with status
  - Top right: Search, Notifications, Settings
```

---

# PART II — SPLASH SCREEN LAYOUT

## 4. The Complete Layout

```
╔════════════════════════════════════════════════════════════════════╗
║ [Avatar] [::]                                  [🔍] [🔔] [⚙]      ║ ← Top bar
║                                                                    ║
║                                                                    ║
║                                                                    ║
║                                          ┌──────────────────────┐ ║
║                                          │ Today's Insight  ✦  │ ║ ← Glass widget
║                                          │ Revenue ↗ +12%      │ ║
║                                          │                     │ ║
║                                          │  AED 17.4M          │ ║
║                                          │                     │ ║
║                                          │  [Explore →]        │ ║
║                                          └──────────────────────┘ ║
║                                                                    ║
║   Good Evening,                                                    ║
║   Ahmed                                  ┌──────────────────────┐ ║
║                                          │ Pending Approvals   │ ║ ← Glass widget
║   What would you like to                 │                     │ ║
║   know today?                            │       3             │ ║
║                                          │                     │ ║
║   ╭──────╮ ╭──────╮ ╭──────╮             │  [Review →]        │ ║
║   │ P&L  │ │ Proj │ │ Cash │             └──────────────────────┘ ║
║   ╰──────╯ ╰──────╯ ╰──────╯                                       ║
║   ╭──────╮ ╭──────╮ ╭──────╮             ┌──────────────────────┐ ║
║   │Reports│ │Voice │ │ More │             │ 📧 Connect Outlook │ ║ ← Integration card
║   ╰──────╯ ╰──────╯ ╰──────╯             │                     │ ║
║                                          │ Sync emails, get    │ ║
║                                          │ insights from your  │ ║
║                                          │ inbox.              │ ║
║                                          │                     │ ║
║                                          │  [Connect Now →]    │ ║
║                                          └──────────────────────┘ ║
║                                                                    ║
║                                                                    ║
║   ◊ Odoo Omni-Agent · Elrace                  [Skip → Open Chat]  ║ ← Footer
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
```

## 5. Background Strategy

### 5.1 Option A: UAE Hero Photography

```
Static high-resolution photo:
  - Abu Dhabi skyline at golden hour
  - Dubai Marina view at sunset
  - Desert dunes with soft light
  - Modern UAE architecture (Etihad Towers, Burj Al Arab silhouette)
  - Construction site (relevant to Elrace business)

Treatment:
  - Slight darkening overlay (20-30% black)
  - Light gradient from bottom (helps text readability)
  - High quality 4K minimum
  - One image per time of day (morning, afternoon, evening, night)
  - Auto-rotates based on local UAE time
```

### 5.2 Option B: Abstract Glass Texture

```
Static abstract:
  - Premium glass surface texture
  - Soft gold/cream gradient
  - Subtle geometric patterns
  - Sophisticated, brand-neutral
  - Minimal distraction

Color palette:
  - Cream white: #faf7f0
  - Soft beige: #f5ede0
  - Pale gold: #e8d5a0
  - Deep navy text: #1a2744
  - Gold accents: #c9a84c
```

### 5.3 Recommended: Both Available

```
User preference in settings:
  - "Hero Photography" (default, more engaging)
  - "Abstract Minimal" (less distraction)
  - "Dark Mode" (premium dark variant)
```

## 6. Time-Based Greeting

```python
GREETINGS = {
    "morning": {
        "en": "Good Morning",
        "ar": "صباح الخير"
    },
    "afternoon": {
        "en": "Good Afternoon",
        "ar": "مساء الخير"
    },
    "evening": {
        "en": "Good Evening",
        "ar": "مساء الخير"
    },
    "night": {
        "en": "Good Evening",  # Stay professional, not "Good Night"
        "ar": "مساء الخير"
    },
}

def get_greeting(user, timezone="Asia/Dubai"):
    hour = datetime.now(timezone).hour
    if 5 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 17:
        time_of_day = "afternoon"
    elif 17 <= hour < 21:
        time_of_day = "evening"
    else:
        time_of_day = "night"
    
    lang = user.language or "en"
    greeting = GREETINGS[time_of_day][lang]
    name = user.name_arabic if lang == "ar" else user.name.split()[0]
    
    return f"{greeting},\n{name}"
```

---

# PART III — COMPONENT SPECIFICATIONS

## 7. Top Bar

```
Left side:
  ┌───────────────────────┐
  │ [Avatar]              │ ← 36px circular, click → profile menu
  │  Ahmed Al-Maktoum     │ ← Name + role on hover
  │  Finance Manager       │
  └───────────────────────┘
  
  [::] grid icon ← apps switcher (future)

Right side:
  [🔍] Search        ← Quick search across system
  [🔔] Notifications ← Badge if unread
  [⚙] Settings      ← Settings menu

Design:
  Glass background: rgba(255,255,255,0.08) blur(20px)
  Border-bottom: 1px solid rgba(255,255,255,0.1)
  Height: 64px
  Padding: 12px 24px
  Position: Fixed top
```

## 8. Greeting Section

```
Position: Left side, center vertically (about 40% from top)

╔═══════════════════════════════════╗
║                                   ║
║  Good Evening,                    ║
║  Ahmed                            ║
║                                   ║
║  What would you like to know      ║
║  today?                           ║
║                                   ║
╚═══════════════════════════════════╝

Typography:
  Greeting:
    Font: Inter or SF Pro Display
    Size: 48px (desktop), 32px (mobile)
    Weight: 300 (Light)
    Color: white (on dark bg) / #1a2744 (on light bg)
    Line height: 1.1
    Letter spacing: -1px
  
  Question:
    Size: 18px
    Weight: 400
    Opacity: 0.7
    Margin top: 16px
```

## 9. Quick Action Pills

```
Below greeting, horizontal flex wrap:

┌────────┐ ┌────────┐ ┌────────┐
│  P&L   │ │Projects│ │ Cash   │
└────────┘ └────────┘ └────────┘
┌────────┐ ┌────────┐ ┌────────┐
│Reports │ │ Voice  │ │ More   │
└────────┘ └────────┘ └────────┘

Pill specifications:
  Background: rgba(255,255,255,0.1)
  Border: 1px solid rgba(255,255,255,0.15)
  Backdrop-filter: blur(16px)
  Border-radius: 100px (pill shape)
  Padding: 10px 20px
  Font: 14px, weight 500
  Color: inherit from theme
  Cursor: pointer
  
Hover state (only animation allowed):
  Background: rgba(255,255,255,0.15)
  Border-color: rgba(255,255,255,0.3)
  Transition: background 0.15s ease
  (NO transform, NO scale, NO bounce)

Active state:
  Background: rgba(201,168,76,0.9) — gold
  Color: #1a2744
  
Behavior:
  Click → opens chat with pre-filled query:
    P&L → "Show me profit and loss"
    Projects → "Show active projects"
    Cash → "Show cash flow this month"
    Reports → "Generate monthly report"
    Voice → opens voice input
    More → expands to show all quick actions
```

## 10. Right-Side Widget Stack

```
Position: Right side, vertically stacked
Width: 280px
Gap between widgets: 16px
Right margin: 32px

Three widgets:

WIDGET 1: Today's Insight
WIDGET 2: Pending Items  
WIDGET 3: Outlook Integration

(see specs below)
```

### 10.1 Widget 1: Today's Insight

```
┌──────────────────────────────┐
│  Today's Insight        ✦    │
│                              │
│  Revenue ↗ +12%              │
│                              │
│  AED 17.4M                   │
│                              │
│  Best month in Q1            │
│                              │
│  [Explore →]                 │
└──────────────────────────────┘

Card spec:
  Background: rgba(255,255,255,0.06)
  Backdrop-filter: blur(24px)
  Border: 1px solid rgba(255,255,255,0.1)
  Border-radius: 20px
  Padding: 24px
  Width: 280px
  
Content:
  Title row: 12px uppercase, opacity 0.5
  ✦ icon: 16px gold
  Trend line: 12px medium, color based on direction (green ↗ / red ↘)
  Big number: 36px light weight
  Description: 13px, opacity 0.7
  CTA button: glass style, gold text

Click behavior:
  → Opens chat with "Tell me about today's revenue"
```

### 10.2 Widget 2: Pending Items

```
┌──────────────────────────────┐
│  Pending Approvals           │
│                              │
│       3                      │
│                              │
│  Invoices waiting review     │
│                              │
│  [Review →]                  │
└──────────────────────────────┘

Same card style as Widget 1.

Content shown based on user role:
  Manager: Pending approvals count
  Top Mgmt: Critical alerts
  User: Suggested next actions
  Admin: System status

Click behavior:
  → Opens relevant chat query or admin panel
```

### 10.3 Widget 3: Outlook Integration (NEW)

```
┌──────────────────────────────┐
│  📧 Connect Outlook          │
│                              │
│  Sync emails, get insights   │
│  from your inbox.            │
│                              │
│  Email:                      │
│  ┌────────────────────────┐  │
│  │ user@elrace.com        │  │
│  └────────────────────────┘  │
│                              │
│  Password / App Code:        │
│  ┌────────────────────────┐  │
│  │ ••••••••••••           │  │
│  └────────────────────────┘  │
│                              │
│  [Connect Securely →]        │
│                              │
│  🔒 Encrypted, never shared   │
│  [What is this?]              │
└──────────────────────────────┘

Same glass card style.

Form fields:
  Background: rgba(255,255,255,0.05)
  Border: 1px solid rgba(255,255,255,0.1)
  Border-radius: 8px
  Padding: 10px 12px
  Color: inherit
  Placeholder: 50% opacity

Connect button:
  Background: linear-gradient(135deg, #c9a84c, #a8873d)
  Color: #1a2744
  Padding: 12px 20px
  Border-radius: 10px
  Font: 14px medium

Trust indicators:
  🔒 icon + "Encrypted, never shared"
  Font: 11px, opacity 0.5
  Link: "What is this?" → opens modal with security info
  
States:
  Default: form visible
  Connecting: shows loading text "Connecting to Microsoft..."
  Connected: shows "✓ Connected to user@elrace.com"
                    with "Disconnect" link
  Failed: shows error with retry button
```

---

# PART IV — OUTLOOK INTEGRATION (FUTURE)

## 11. Authentication Approach

```
Recommended: Microsoft OAuth 2.0
  - Not raw username/password (insecure)
  - Use Microsoft Graph API
  - Industry standard
  - User consents via Microsoft login page
  - Returns access token + refresh token

Flow:
  1. User clicks "Connect Outlook"
  2. Splash form just collects email (validation)
  3. Click "Connect Securely" 
  4. Opens Microsoft OAuth popup
  5. User signs into Microsoft (their existing session)
  6. Microsoft asks: "Allow OOA to read your emails?"
  7. User approves
  8. Returns to splash with "Connected"
  9. Tokens stored encrypted in our DB
  10. Refresh token auto-refreshes access
```

## 12. Why Not Direct Password?

```
Problem with raw password:
  ❌ Users have MFA enabled → password alone doesn't work
  ❌ Storing passwords (even encrypted) is risky
  ❌ Password changes break the integration
  ❌ Microsoft is actively phasing out basic auth
  ❌ Compliance issue for enterprise
  
OAuth advantages:
  ✓ Works with MFA
  ✓ Granular permissions
  ✓ Tokens can be revoked
  ✓ No password storage
  ✓ Microsoft handles security
```

## 13. UI Adaptation for OAuth

```
Replace password field with OAuth flow:

┌──────────────────────────────┐
│  📧 Connect Outlook          │
│                              │
│  Sync emails for AI insights │
│                              │
│  Email (Optional):           │
│  ┌────────────────────────┐  │
│  │ user@elrace.com        │  │
│  └────────────────────────┘  │
│                              │
│  [Sign in with Microsoft →]  │
│                              │
│  🔒 Secure OAuth — no        │
│     password needed          │
└──────────────────────────────┘

Click button:
  → Opens Microsoft login popup
  → User completes Microsoft auth
  → Returns to splash
  → "Connected ✓ user@elrace.com"
```

## 14. What Outlook Integration Will Do

```
After connection (future features):
  
1. EMAIL DIGEST
   AI scans inbox daily
   Summarizes important emails
   Flags emails needing response
   
2. MEETING PREP
   "Show me emails from Abu Dhabi Police"
   "Summarize this week's correspondence with vendors"
   
3. INVOICE TRACKING
   Detects invoice emails
   Links them to Odoo records
   Alerts on missing approvals
   
4. CALENDAR INTEGRATION
   "What's on my calendar today?"
   "Schedule a review with finance"
   "Find time with the team"
   
5. ACTION ITEMS
   AI extracts action items from emails
   Creates tasks
   Sends reminders
   
6. SMART REPLIES
   AI drafts professional replies
   Context-aware
   Multi-language
```

---

# PART V — SKIP TO CHAT FUNCTIONALITY

## 15. Skip Button

```
Position: Bottom right of splash screen
         Or center bottom

Design:
  Subtle, not pushy
  Glass button with gold text
  
Text variations:
  "Skip → Open Chat"
  "Go to AI Chat →"
  "Continue to Assistant →"
  "Just open the chat →"

Behavior:
  Click → instant transition to chat screen
  No animation (per requirements)
  Just direct navigation
  
Keyboard:
  Press Esc → skips
  Press Enter on main area → skips
```

## 16. First Visit vs Returning User

```
FIRST VISIT (no localStorage flag):
  Splash screen shows full experience
  Highlights Outlook integration card
  Shows tutorial hints (subtle)
  "Get Started" instead of "Skip"
  
RETURNING USER:
  Splash still shown by default
  But quicker access — auto-skip option in settings
  Settings: ☐ Skip splash screen on launch
  
RETURNING WITH AUTO-SKIP:
  Splash flashes briefly (200ms)
  Then goes to chat
  Provides "open splash" option in chat
```

## 17. State Persistence

```javascript
// On splash → chat transition
localStorage.setItem("ooa_has_visited", "true");
localStorage.setItem("ooa_last_splash_action", "skipped"); // or "pill_clicked"

// On settings change
const autoSkip = localStorage.getItem("ooa_auto_skip_splash") === "true";

// On app load
const showSplash = !autoSkip || isFirstVisit;
if (!showSplash) {
  navigate("/chat");
}
```

---

# PART VI — SHOWCASE ELEMENTS

## 18. What to Showcase Beyond Widgets

### 18.1 Subtle Stats Bar (Optional)

```
Below the greeting area:

  ┌──────────────────────────────────────────┐
  │ ✓ 247 queries today  ✓ 18 reports        │
  │   generated  ✓ Connected to Odoo Live    │
  └──────────────────────────────────────────┘

Design:
  Single line of small text
  Icon prefixes
  Subtle gold checkmarks
  Color: opacity 0.6
  Font: 12px
  No background, just text

Purpose:
  Builds trust
  Shows the system is alive
  Subtle social proof
```

### 18.2 Recent Reports Preview (Optional)

```
Below right widgets, smaller card:

  ┌──────────────────────────────┐
  │  Recent Reports              │
  │  ─────────────────────────── │
  │  📄 April P&L Report          │
  │     Generated 2 hours ago    │
  │  ─────────────────────────── │
  │  📊 Q1 Performance Excel     │
  │     Generated yesterday      │
  │  ─────────────────────────── │
  │  [View All Reports →]        │
  └──────────────────────────────┘

Shows continuity
Encourages re-engagement
Click → opens report
```

### 18.3 AI Capability Spotlight

```
Rotating capability highlight (text only, no rotation animation):

  Display once based on day of week or random selection:
  
  Monday:    "💡 Did you know? Ask in Arabic anytime."
  Tuesday:   "💡 Generate PDFs by saying 'create report'"
  Wednesday: "💡 Drag any answer to Visualize for export"
  Thursday:  "💡 Voice queries work in both languages"
  Friday:    "💡 Get email summaries via Outlook integration"
  
Small text below pills, subtle:
  Font: 12px italic
  Opacity: 0.5
  
Educational without being intrusive.
```

---

# PART VII — RESPONSIVE BEHAVIOR

## 19. Mobile Layout

```
On mobile (< 768px):

╔═══════════════════════╗
║  [Avatar]  [🔍][🔔]  ║
║                       ║
║                       ║
║  Good Evening,        ║
║  Ahmed                ║
║                       ║
║  What would you       ║
║  like to know?        ║
║                       ║
║  ╭───╮ ╭───╮ ╭───╮    ║
║  │P&L│ │Prj│ │Cash│   ║
║  ╰───╯ ╰───╯ ╰───╯    ║
║                       ║
║  Stacked widgets:     ║
║  ┌─────────────────┐  ║
║  │ Today's Insight │  ║
║  └─────────────────┘  ║
║  ┌─────────────────┐  ║
║  │ Pending: 3      │  ║
║  └─────────────────┘  ║
║  ┌─────────────────┐  ║
║  │ Connect Outlook │  ║
║  └─────────────────┘  ║
║                       ║
║  [Open Chat →]        ║
╚═══════════════════════╝

Adaptations:
  - Widgets stack below greeting
  - Pills wrap to 2-3 per row
  - Greeting stays large
  - Touch-friendly tap targets (44px min)
  - No hover states (use active state)
```

## 20. Tablet Layout

```
On tablet (768-1200px):
  - Same as desktop but tighter
  - Widget width reduces to 240px
  - Pills can be 4 per row
  - Greeting slightly smaller (40px)
```

---

# PART VIII — IMPLEMENTATION

## 21. Component Structure

```
ooa-ui/src/splash/
├── SplashScreen.jsx           # Main container
├── HeroBackground.jsx         # Static image background
├── TopBar.jsx                 # Avatar + search + notifications
├── GreetingSection.jsx        # Welcome text + question
├── QuickActionPills.jsx       # Pill buttons
├── WidgetStack.jsx            # Right side widgets
├── widgets/
│   ├── InsightWidget.jsx      # Today's insight
│   ├── PendingWidget.jsx      # Pending items
│   └── OutlookWidget.jsx      # Outlook integration
├── SkipButton.jsx             # Bottom skip button
└── StatsBar.jsx               # Optional subtle stats
```

## 22. Code Skeleton

```jsx
// SplashScreen.jsx

function SplashScreen({ user, onSkipToChat }) {
  const greeting = getGreeting(user);
  
  return (
    <div className="splash-screen">
      <HeroBackground variant={user.preference || "photography"} />
      
      <TopBar user={user} />
      
      <div className="splash-content">
        <div className="left-section">
          <GreetingSection greeting={greeting} />
          <QuickActionPills onPillClick={handlePillClick} />
          <StatsBar /> {/* Optional */}
        </div>
        
        <div className="right-section">
          <WidgetStack>
            <InsightWidget data={todaysInsight} />
            <PendingWidget count={pendingCount} />
            <OutlookWidget connected={outlookConnected} />
          </WidgetStack>
        </div>
      </div>
      
      <SkipButton onClick={onSkipToChat} />
    </div>
  );
}
```

## 23. Styles (Static, No Motion)

```css
/* splash.css */

.splash-screen {
  position: fixed;
  inset: 0;
  background: var(--splash-bg);
  overflow: hidden;
  /* NO transitions on entry */
}

.hero-background {
  position: absolute;
  inset: 0;
  background-image: url(/images/uae-skyline.jpg);
  background-size: cover;
  background-position: center;
  z-index: 0;
}

.hero-background::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    rgba(0,0,0,0.2) 0%,
    rgba(0,0,0,0.5) 100%
  );
}

.splash-content {
  position: relative;
  z-index: 10;
  height: 100vh;
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 48px;
  padding: 80px 48px 48px 48px;
}

.greeting {
  font-size: 48px;
  font-weight: 300;
  line-height: 1.1;
  color: white;
  margin-bottom: 16px;
  letter-spacing: -1px;
}

.greeting-question {
  font-size: 18px;
  opacity: 0.7;
  color: white;
  margin-bottom: 32px;
}

.action-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  max-width: 480px;
}

.pill {
  padding: 10px 20px;
  border-radius: 100px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.15);
  backdrop-filter: blur(16px);
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease; /* ONLY allowed transition */
}

.pill:hover {
  background: rgba(255,255,255,0.15);
  /* NO transform, NO scale */
}

.widget {
  background: rgba(255,255,255,0.06);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 20px;
  padding: 24px;
  margin-bottom: 16px;
}

.widget-title {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.5;
  margin-bottom: 12px;
  color: white;
}

.widget-value {
  font-size: 36px;
  font-weight: 300;
  color: white;
  margin-bottom: 8px;
}

.widget-description {
  font-size: 13px;
  opacity: 0.7;
  color: white;
  margin-bottom: 16px;
}

.widget-cta {
  font-size: 13px;
  color: #c9a84c;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
  /* NO underline, NO bold transitions */
}

/* Outlook widget specific */
.outlook-form input {
  width: 100%;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  padding: 10px 12px;
  color: white;
  font-size: 14px;
  margin-bottom: 12px;
}

.outlook-form input:focus {
  outline: none;
  border-color: rgba(201,168,76,0.5);
  /* NO box-shadow animation, just color change */
}

.connect-button {
  width: 100%;
  background: linear-gradient(135deg, #c9a84c, #a8873d);
  color: #1a2744;
  padding: 12px;
  border-radius: 10px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease;
}

.connect-button:hover {
  background: linear-gradient(135deg, #d4b35c, #b8964a);
}

.skip-button {
  position: absolute;
  bottom: 32px;
  right: 32px;
  background: rgba(255,255,255,0.08);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,0.1);
  color: #c9a84c;
  padding: 12px 24px;
  border-radius: 100px;
  font-size: 14px;
  cursor: pointer;
}
```

---

# PART IX — TWO COLOR VARIANTS

## 24. Light Variant

```
For users who prefer light contrast:

Background:
  Linear gradient: #faf7f0 → #f5ede0 → #e8d5a0 (cream tones)
  OR static cream texture

Text colors:
  Primary: #1a2744 (deep navy)
  Secondary: #5a6378
  
Glass panels:
  background: rgba(255,255,255,0.6)
  border: rgba(255,255,255,0.8)
  backdrop-filter: blur(24px)

Same layout, just inverted colors.
```

## 25. Dark Variant (Like Reference)

```
Background:
  Hero photo with darkening overlay
  Or solid dark navy: #0a0f1e

Text colors:
  Primary: white
  Secondary: rgba(255,255,255,0.7)

Glass panels:
  background: rgba(255,255,255,0.06)
  border: rgba(255,255,255,0.1)
  backdrop-filter: blur(24px)
```

## 26. Toggle Location

```
Settings menu (⚙ in top right):
  
  Theme:
  ○ Light (cream + dark text)
  ● Dark (hero photo + white text)
  ○ Auto (matches system)

Persist in localStorage and user profile.
```

---

# PART X — ACCESSIBILITY

## 27. A11y Requirements

```
✓ Color contrast: WCAG AA minimum
  Greeting text vs background: 7:1
  Body text: 4.5:1
  
✓ Keyboard navigation
  Tab through all interactive elements
  Enter activates buttons
  Esc skips to chat
  
✓ Screen reader friendly
  Semantic HTML
  ARIA labels on icons
  Alt text on hero image (or aria-hidden)
  
✓ Reduced motion
  Already no motion, but respect prefers-reduced-motion
  
✓ Focus indicators
  Visible focus ring on all interactive elements
  Use gold color: 2px solid #c9a84c
  
✓ Touch targets
  Minimum 44x44px on mobile
  Pills are tall enough
  Widgets fully clickable
  
✓ Language attributes
  lang="ar" on Arabic text
  dir="rtl" on Arabic sections
```

---

# PART XI — IMPLEMENTATION PHASES

## 28. Build Order

### Phase 1 — Base Layout (Week 1)
```
[ ] Set up SplashScreen component
[ ] Implement hero background (photo)
[ ] Add darkening overlay
[ ] Build top bar (avatar, icons)
[ ] Build greeting section
[ ] Test layout on different screen sizes
```

### Phase 2 — Quick Action Pills (Week 1)
```
[ ] Build pill component
[ ] Style with glass effect
[ ] Add hover state (background only)
[ ] Wire click → navigate to chat with pre-filled query
[ ] Add icons to pills
```

### Phase 3 — Right Widgets (Week 2)
```
[ ] Build glass widget container
[ ] Insight widget with real data
[ ] Pending items widget
[ ] Widget click navigation
[ ] API endpoint for widget data
```

### Phase 4 — Outlook Widget UI (Week 2)
```
[ ] Build Outlook widget form
[ ] Add email/password inputs (static UI)
[ ] Add trust indicators
[ ] Add "What is this?" modal
[ ] No backend yet — just UI
```

### Phase 5 — Skip & Navigation (Week 3)
```
[ ] Build skip button
[ ] Wire to chat navigation
[ ] Persist user state
[ ] Add auto-skip preference
[ ] Test full flow: load → skip → chat
```

### Phase 6 — Themes & Polish (Week 3)
```
[ ] Implement light variant
[ ] Implement dark variant
[ ] Settings toggle
[ ] Time-based greeting
[ ] Language support (Arabic RTL)
```

### Phase 7 — Outlook OAuth Backend (Future, Week 4-5)
```
[ ] Register app in Microsoft Azure
[ ] Get client ID + secret
[ ] OAuth flow endpoints
[ ] Token storage (encrypted)
[ ] Token refresh logic
[ ] Microsoft Graph API integration
[ ] Email sync logic
[ ] AI processing of emails
```

---

# PART XII — QUALITY STANDARDS

## 29. What "Done" Looks Like

```
✓ Page loads instantly (< 1s)
✓ Hero image high quality, properly sized
✓ Greeting personalized (uses real name)
✓ Time-based greeting accurate (UAE timezone)
✓ Pills clickable and navigate correctly
✓ Widgets show real data (not placeholder)
✓ Outlook UI form looks professional
✓ Skip button works from anywhere
✓ Mobile layout doesn't break
✓ Arabic RTL works correctly
✓ NO motion animations anywhere
✓ Smooth hover states only
✓ Glass effects render cleanly
✓ Light and dark variants both work
✓ Accessibility standards met
```

---

# PART XIII — TELL CURSOR

```
"Read SPLASH_SCREEN_PLAN.md.

Start Phase 1: Build the base layout.

1. Create ooa-ui/src/splash/ folder
2. Build SplashScreen.jsx with hero background
3. Add top bar with avatar
4. Add greeting section with time-based logic
5. Test on desktop browser

Critical rules:
- NO motion animations
- ONLY hover state transitions allowed (background color only)
- Use glass effects (backdrop-filter)
- High contrast for readability
- Static design throughout

Reference:
- The user's screenshot for layout inspiration
- V1.2_UI_LAYOUT.md for component patterns
- PRODUCT_QUALITY_FRAMEWORK.md for quality bar

After Phase 1, move to Phase 2 (Quick Action Pills).

Note: This is a redesign — do NOT keep old splash code.
Build fresh in /splash/ folder."
```

---

# PART XIV — NEXT STEPS

After this splash screen is built and tested:

```
We will then plan:
  - Inside screens (chat interface redesign)
  - Apply same clean white contrast glassy style
  - No motions throughout
  - Consistent design language
  
For now:
  - Focus only on splash
  - Get the look right
  - User can skip into existing chat (still old design)
  - We will redesign chat next
```

# SPLASH SCREEN PLAN v2 — REFINED

> **Major Change:** Splash screen is now a SINGLE unified screen. Login state is just an overlay change. No separate login page. Logged-in features (insights, approvals) always show. After login, user name appears in header, Outlook popup replaces input area.

> **Read first:** `SPLASH_SCREEN_PLAN.md` (original), `MAIN_SCREENS_LAYOUT_PLAN.md`

---

# PART I — KEY CHANGES FROM v1

## 1. What Changed and Why

```
v1 PROBLEM (from screenshot):
  ❌ Logged-out screen is empty/sparse
  ❌ Only shows login card
  ❌ Looks "not good" — user feedback
  ❌ Two separate screens (login + splash)

v2 SOLUTION:
  ✓ ONE unified screen always
  ✓ All features visible (insights, approvals, etc.)
  ✓ Login is an OVERLAY popup, not a separate screen
  ✓ Background is consistent across all states
  ✓ Smooth state transition when logged in
```

## 2. The Three States of One Screen

```
STATE 1: NOT LOGGED IN
  - Full splash visible
  - Greeting: "Good Afternoon" (no name)
  - All widgets visible (Today's Insight, Pending, etc.)
  - Where Outlook widget was → File ID login form
  - "Skip → Open Chat" hidden (login required first)

STATE 2: LOGGING IN (transition)
  - Same layout, no flash
  - Login button shows "Verifying..."
  - Smooth UI update

STATE 3: LOGGED IN
  - Same layout, no reload
  - Header now shows: "SA Super Administrator" / role
  - Greeting completes: "Good Afternoon Super"
  - Login form replaced by Outlook connector popup
  - "Skip → Open Chat" button visible
  - Footer shows "◊ Odoo Omni-Agent · Elrace"
```

---

# PART II — UNIFIED LAYOUT (BOTH STATES)

## 3. Single Layout, Different Content

```
╔════════════════════════════════════════════════════════════════════╗
║ HEADER (consistent with body, no different contrast)              ║
║                                                                    ║
║ [Avatar Initial]  Super Administrator     [::]  [🔍] [🔔] [⚙]    ║
║                   super_admin                                      ║
║                                                                    ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║                                          ┌──────────────────────┐ ║
║                                          │  TODAY'S INSIGHT  ✦ │ ║
║                                          │  Revenue ↗ +12%    │ ║
║                                          │                     │ ║
║                                          │  AED 17.4M          │ ║
║                                          │  Best month in Q1   │ ║
║                                          │                     │ ║
║                                          │  Explore →          │ ║
║                                          └──────────────────────┘ ║
║                                                                    ║
║                                          ┌──────────────────────┐ ║
║  Good Afternoon                          │  PENDING APPROVALS  │ ║
║  Super                                   │                     │ ║
║                                          │      3              │ ║
║  What would you like to know today?      │  Invoices waiting   │ ║
║                                          │                     │ ║
║  ╭─────╮ ╭─────╮ ╭─────╮ ╭─────╮         │  Review →           │ ║
║  │ P&L │ │Proj │ │Cash │ │Rpts │         └──────────────────────┘ ║
║  ╰─────╯ ╰─────╯ ╰─────╯ ╰─────╯                                  ║
║  ╭─────╮ ╭─────╮                         ┌──────────────────────┐ ║
║  │Voice│ │More │                         │  📧 CONNECT OUTLOOK │ ║
║  ╰─────╯ ╰─────╯                         │                     │ ║
║                                          │  Sync emails, get   │ ║
║  Connect Outlook to unlock insights      │  insights from your │ ║
║                                          │  inbox.             │ ║
║  ✓ 247 queries today                     │                     │ ║
║  ✓ 18 reports generated                  │  Email              │ ║
║  ✓ Connected to Odoo Live                │  ┌────────────────┐ │ ║
║                                          │  │ user@elrace.com│ │ ║
║                                          │  └────────────────┘ │ ║
║                                          │                     │ ║
║                                          │  [Connect →]        │ ║
║                                          │            [Skip →] │ ║
║                                          └──────────────────────┘ ║
║                                                                    ║
║ ◊ Odoo Omni-Agent · Elrace             [Skip → Open Chat]         ║
╚════════════════════════════════════════════════════════════════════╝
```

---

# PART III — HEADER (UNIFIED, NO DIFFERENT CONTRAST)

## 4. Header Design

```
CRITICAL: Header background MUST match body background.
No different contrast. No solid bar. Seamless.

Structure:
  ┌─────────────────────────────────────────────────────────┐
  │ [SA]  Super Administrator                               │
  │       super_admin              [::] [🔍] [🔔] [⚙]      │
  └─────────────────────────────────────────────────────────┘

Specifications:
  Background: TRANSPARENT (no bar, no different bg)
  Padding: 24px 32px
  Position: Absolute top
  No border-bottom
  No backdrop-filter
  Just floats over the body
```

## 5. User Profile Block (Top Left)

```
LOGGED OUT STATE:
  [User icon] Guest
              Not logged in

LOGGED IN STATE:
  [SA initials circle] Super Administrator
                       super_admin

Specifications:
  Avatar circle: 40px, gold border
  Initials: 16px, gold text
  Name: 16px, weight 500
  Subtitle (role): 12px, opacity 0.6
  Gap between avatar and text: 12px
```

## 6. Top Right Utility Icons

```
[::]  Apps switcher (grid icon)
[🔍] Search
[🔔] Notifications (with badge if unread)
[⚙] Settings

Icon specifications:
  Each: 36x36 circular
  Background: rgba(255,255,255,0.06)
  No border (cleaner)
  Hover: rgba(255,255,255,0.1)
  Spacing: 8px between
```

---

# PART IV — STATE 1: NOT LOGGED IN

## 7. Greeting Section (Logged Out)

```
LEFT SIDE:

  Good Afternoon                ← 64px, weight 200 (extra light)
  
  Welcome                       ← 64px, weight 200
  
  What would you like to        ← 16px, weight 400, opacity 0.7
  know today?

Time-based greeting:
  Morning (5-12):   "Good Morning"
  Afternoon (12-17): "Good Afternoon"
  Evening (17-21):  "Good Evening"
  Night (21-5):     "Good Evening"

Second line when NOT logged in:
  "Welcome" (English)
  "أهلاً وسهلاً" (Arabic)
```

## 8. Action Pills (Always Visible)

```
Pills available even when not logged in:
  
  ╭─────╮ ╭─────╮ ╭─────╮ ╭─────╮
  │ P&L │ │Proj │ │Cash │ │Rpts │
  ╰─────╯ ╰─────╯ ╰─────╯ ╰─────╯
  ╭─────╮ ╭─────╮
  │Voice│ │More │
  ╰─────╯ ╰─────╯

Behavior when NOT logged in:
  Click pill → triggers login popup
  After login → executes the action

Behavior when LOGGED IN:
  Click pill → opens chat with pre-filled query
```

## 9. Right Side Widgets (Always Visible)

```
Even when NOT logged in, show these widgets:

WIDGET 1: Today's Insight
  Shows generic/demo data when logged out
  e.g., "Revenue ↗ +12% — Sample insight"
  Click → triggers login popup
  
  OR: Show real data once logged in
  
WIDGET 2: Pending Approvals
  Shows "—" or "Sign in to view" when logged out
  Shows real count when logged in
  
WIDGET 3: Login Form (when logged out) 
       OR Connect Outlook (when logged in)
```

## 10. Login Widget (Replaces Outlook When Logged Out)

```
WHEN NOT LOGGED IN, third widget shows:

┌──────────────────────────────────┐
│  🔐 SIGN IN                      │
│                                  │
│  Welcome to Elrace AI            │
│  Your Intelligent ERP Companion  │
│                                  │
│  FILE ID                         │
│  ┌────────────────────────────┐  │
│  │  Enter your File ID        │  │
│  │  e.g., 2721                │  │
│  └────────────────────────────┘  │
│                                  │
│  [Sign In →]                     │
│                                  │
│  Use your Elrace File ID         │
│  to continue                     │
└──────────────────────────────────┘

Specifications:
  Same glass card as other widgets
  Input field: with gold focus border
  Sign In button: gold gradient
  Footer text: 12px, opacity 0.6
```

## 11. Bottom Footer (Logged Out)

```
LEFT: ◊ Odoo Omni-Agent · Elrace
RIGHT: [hidden — no skip until logged in]

Or alternative:
  RIGHT: "Need help? Contact Admin"
```

---

# PART V — STATE 3: LOGGED IN

## 12. What Changes After Login

```
Header:
  Shows user name and role
  Avatar shows initials with gold color
  
Greeting:
  "Good Afternoon" stays
  Second line: User's first name (large)
  
Widgets:
  Today's Insight → Shows real data
  Pending Approvals → Real count
  Outlook Widget → Replaces login widget (popup style)
  
Footer:
  "Skip → Open Chat" button appears (gold)
```

## 13. Outlook Connector Popup (After Login)

```
After successful login, the THIRD widget transforms into:

┌──────────────────────────────────┐
│  📧 CONNECT OUTLOOK              │
│                                  │
│  Sync emails, get insights from  │
│  your inbox.                     │
│                                  │
│  Email                           │
│  ┌────────────────────────────┐  │
│  │ user@elrace.com            │  │
│  └────────────────────────────┘  │
│                                  │
│  Password / App Code             │
│  ┌────────────────────────────┐  │
│  │ ●●●●●●●●●●●●               │  │
│  └────────────────────────────┘  │
│                                  │
│  [Connect Securely →]            │
│              [Skip →]            │
│                                  │
│  🔒 Encrypted, never shared      │
│  [What is this?]                 │
└──────────────────────────────────┘

Transition (no flash):
  Login widget fades out
  Outlook widget fades in (same position)
  Duration: 200ms
  
This is the ONLY allowed transition.
```

## 14. Skip Behavior

```
TWO skip locations:

A) Inside Outlook widget: [Skip →]
   - Closes Outlook popup
   - Stays on splash screen
   - Outlook widget shows "Skipped — Connect later" state

B) Bottom right: [Skip → Open Chat]
   - Goes to main chat screen
   - Outlook can be connected later from settings
```

---

# PART VI — TYPOGRAPHY SYSTEM (SMART CHOICES)

## 15. Type Scale

```
DISPLAY (Hero greeting):
  Font size: 64px desktop, 48px tablet, 36px mobile
  Weight: 200 (ExtraLight)
  Line height: 1.1
  Letter spacing: -1.5px (tight, modern)
  Color: var(--text-primary)
  
HEADING 1 (Widget titles like "TODAY'S INSIGHT"):
  Font size: 11px
  Weight: 600 (SemiBold)
  Letter spacing: 1.5px (wide, uppercase feel)
  Text transform: uppercase
  Color: var(--text-muted) — opacity 0.6
  
HEADING 2 (Big numbers like "AED 17.4M"):
  Font size: 40px
  Weight: 300 (Light)
  Letter spacing: -0.5px
  Color: var(--text-primary)
  Numbers: tabular-nums for alignment
  
BODY (Descriptions):
  Font size: 14px
  Weight: 400 (Regular)
  Line height: 1.5
  Color: var(--text-secondary)
  
BODY EMPHASIS (italic call-outs):
  Font size: 14px
  Weight: 400
  Font style: italic
  Color: var(--text-muted) — opacity 0.7
  Used for: "Connect Outlook to unlock inbox insights"
  
LABELS (Form labels):
  Font size: 12px
  Weight: 500 (Medium)
  Letter spacing: 0.5px
  Color: var(--text-secondary)
  
BUTTONS / PILLS:
  Font size: 14px
  Weight: 500 (Medium)
  Letter spacing: 0
  
SMALL / META (timestamps, hints):
  Font size: 12px
  Weight: 400
  Color: var(--text-muted) — opacity 0.5
  
TRUST INDICATORS (checkmarks list):
  Font size: 13px
  Weight: 400
  Color: var(--text-muted) — opacity 0.6
```

## 16. Weight Usage Rules

```
WHEN TO USE WHICH WEIGHT:

200 ExtraLight:
  ✓ Large display text (greeting "Good Afternoon")
  ✓ Hero numbers if very large
  
300 Light:
  ✓ Big numbers (KPIs like "AED 17.4M")
  ✓ Card titles
  
400 Regular:
  ✓ Body text
  ✓ Descriptions
  ✓ Most UI text
  
500 Medium:
  ✓ Labels
  ✓ Button text
  ✓ User names
  
600 SemiBold:
  ✓ Section headings ("TODAY'S INSIGHT")
  ✓ Important emphasis
  
700 Bold:
  ✓ Critical alerts only
  ✓ Total numbers in tables
  ✗ Avoid for general use (looks heavy)
```

## 17. Italic Usage

```
USE ITALIC FOR:
  ✓ Hints/tips: "Connect Outlook to unlock inbox insights."
  ✓ Definitions: "Less:  Sales Return"
  ✓ Quotes
  ✓ Foreign words in same-language context
  
DO NOT USE ITALIC FOR:
  ✗ Headers
  ✗ Buttons
  ✗ Numbers
  ✗ Long body text
```

---

# PART VII — LIGHT THEME: SKY BLUE (Not Cream)

## 18. Sky Blue Light Theme

```
REPLACING the cream variant from v1 with sky blue.

BACKGROUND:
  Primary: linear-gradient(180deg,
    #e0eaf5 0%,      /* Pale sky blue top */
    #c5d9ee 50%,     /* Mid sky blue */
    #a8c5e0 100%     /* Deeper sky blue bottom */
  );
  
  Optional: Add subtle hero photography behind
            (UAE blue sky, clouds, mountains)
            With darkening overlay for text readability
  
TEXT:
  Primary: #1a2744 (deep navy — same as before)
  Secondary: #4a5778 (lighter navy-gray)
  Muted: rgba(26, 39, 68, 0.5)
  
GLASS PANELS:
  Background: rgba(255, 255, 255, 0.55)
  Border: rgba(255, 255, 255, 0.7)
  Backdrop-filter: blur(24px)
  Shadow: 0 8px 32px rgba(26, 39, 68, 0.08)
  
ACCENTS:
  Primary gold: #c9a84c (keep gold for buttons)
  Secondary: #4ecdc4 (cyan for trends)
  Alert: #ef4444 (red)
  Success: #10b981 (green)
  
HEADER (transparent over sky):
  No background color
  Just floating elements
  Text color matches body
```

## 19. Three Theme Variants

```
THEME 1: SKY BLUE (Light) — new default
  Background: Sky blue gradient
  Text: Deep navy
  Glass: White with high opacity
  Feel: Fresh, professional, daytime
  
THEME 2: DARK (Black/Navy)
  Background: #0a0f1e (deep dark)
  Text: White
  Glass: White with low opacity
  Feel: Premium, focused, evening
  
THEME 3: ABSTRACT
  Background: Subtle abstract gradient
  Soft purple to gold transitions
  Text: Adaptive based on background
  Feel: Sophisticated, brand-neutral
  
SELECTION:
  Settings menu → Theme
  Persists in localStorage
  Auto option: matches system preference
```

## 20. Dark Theme (Stays as Reference Screenshot)

```
This is the current screenshot — the dark theme.
Keep this exactly as shown.

  Background: #0a0f1e with subtle gradient
  Text: White
  Cards: rgba(255,255,255,0.04) with blur
  Header: transparent (same as body)
  Greeting: White, ExtraLight weight
```

---

# PART VIII — REFINED LAYOUT SPECIFICATIONS

## 21. Spacing System

```
Container padding (left/right):
  Desktop: 48px
  Tablet: 32px
  Mobile: 20px

Top spacing:
  Header height: 88px (including avatar)
  Body top: starts at 120px from top (under header)

Right widget column:
  Width: 320px
  Right margin: 48px
  Top margin: 120px (aligned with body)
  Gap between widgets: 20px

Left content column:
  Max width: 600px
  Greeting bottom margin: 32px
  Pills top margin: 24px

Bottom:
  Footer height: 80px (fixed)
  Footer padding: 32px 48px
```

## 22. Pills Spacing & Wrapping

```
Pills layout:
  Display: flex
  Flex-wrap: wrap
  Gap: 12px
  Max width: 480px

Pill specifications:
  Padding: 12px 24px
  Min-width: auto (content-based)
  Background: rgba(255,255,255,0.08)
  Border: 1px solid rgba(255,255,255,0.12)
  Border-radius: 100px
  Font: 14px medium
  
Hover:
  Background: rgba(255,255,255,0.12)
  No transform, no scale
```

## 23. Widget Specifications

```
Widget card:
  Width: 320px (fixed)
  Min-height: variable
  Background: rgba(255,255,255,0.06)
  Backdrop-filter: blur(24px)
  Border: 1px solid rgba(255,255,255,0.1)
  Border-radius: 24px
  Padding: 24px
  
Internal spacing:
  Title margin-bottom: 12px
  Big number margin-bottom: 8px
  Description margin-bottom: 16px
  CTA: aligned to start
  
CTA link style:
  Color: #c9a84c (gold)
  Font: 14px medium
  Background: transparent
  No underline
  Hover: brightness 1.1
```

---

# PART IX — TRUST INDICATORS REFINED

## 24. Stats Display

```
LEFT SIDE, below pills, italic style:

  "Connect Outlook to unlock inbox insights."
  ← italic, 14px, opacity 0.6
  
  ✓ 247 queries today  ✓ 18 reports generated  ✓ Connected to Odoo Live
  ← single line, 13px, opacity 0.5
  ← checkmarks in gold
  ← gap between items: 16px
  
ALIGNMENT:
  Same left margin as greeting
  Top margin from pills: 32px
```

---

# PART X — INTERACTIONS & STATE TRANSITIONS

## 25. Login Flow (No Page Reload)

```
SEQUENCE:

1. User enters File ID
2. Click "Sign In →"
3. Button shows "Verifying..." (text change only)
4. Backend validates
5. SUCCESS path:
   a) Avatar appears in header (with initials)
   b) Name appears: "Super Administrator"
   c) Greeting completes: "Good Afternoon" → "Good Afternoon Super"
   d) Today's Insight widget updates with real data
   e) Pending Approvals shows real count
   f) Login widget fades out (200ms)
   g) Outlook widget fades in (200ms) — at same position
   h) "Skip → Open Chat" button appears in footer
6. FAILURE path:
   a) Input border turns red briefly
   b) Error text appears below: "File ID not recognized"
   c) User retries
```

## 26. Animation Policy (Strict)

```
ONLY ALLOWED ANIMATIONS:

✓ Login → Outlook widget swap: 200ms cross-fade
✓ Hover background changes: 150ms ease
✓ Focus border changes: 150ms ease
✓ Button text changes (instant)
✓ Click feedback: opacity 0.8 briefly (50ms)

FORBIDDEN:
✗ Background gradient animations
✗ Particle effects
✗ Bob/float animations
✗ Card slide-in animations
✗ Greeting typewriter effect
✗ Pills wave animation
✗ Anything decorative

The page should feel STATIC AND PREMIUM.
Like a well-designed corporate website.
```

---

# PART XI — COMPONENT IMPLEMENTATION

## 27. React Structure

```
ooa-ui/src/splash/
├── SplashScreen.jsx              # Main container, state mgmt
├── SplashHeader.jsx              # Transparent header
├── ProfileBlock.jsx              # SA avatar + name + role
├── UtilityIcons.jsx              # Search, notifications, settings
├── GreetingSection.jsx           # Time-based greeting + name
├── QuickActionPills.jsx          # P&L, Projects, etc.
├── TrustIndicators.jsx           # Italic hint + checkmarks
├── WidgetStack.jsx               # Right side container
│   ├── TodaysInsightWidget.jsx
│   ├── PendingApprovalsWidget.jsx
│   ├── LoginWidget.jsx           # Shown when not logged in
│   └── OutlookConnectorWidget.jsx # Shown when logged in
├── SplashFooter.jsx              # Branding + Skip button
└── styles/
    └── splash.css
```

## 28. State Management

```jsx
// SplashScreen.jsx

function SplashScreen() {
  const [user, setUser] = useState(null);
  const [loginState, setLoginState] = useState("logged_out"); 
  // "logged_out" | "verifying" | "logged_in"
  const [outlookSkipped, setOutlookSkipped] = useState(false);
  
  const isLoggedIn = user !== null;
  
  const handleLoginSubmit = async (fileId) => {
    setLoginState("verifying");
    try {
      const userData = await api.login(fileId);
      setUser(userData);
      setLoginState("logged_in");
      // Stay on splash screen
    } catch (err) {
      setLoginState("logged_out");
      // Show error
    }
  };
  
  const handleSkipToChat = () => {
    navigate("/chat");
  };
  
  return (
    <div className="splash-screen">
      <SplashHeader 
        user={user} 
        isLoggedIn={isLoggedIn} 
      />
      
      <div className="splash-body">
        <div className="left-column">
          <GreetingSection 
            user={user}
            isLoggedIn={isLoggedIn}
          />
          <QuickActionPills 
            isLoggedIn={isLoggedIn}
            onPillClick={isLoggedIn ? handlePillClick : showLoginPrompt}
          />
          <TrustIndicators
            isLoggedIn={isLoggedIn}
          />
        </div>
        
        <div className="right-column">
          <TodaysInsightWidget user={user} />
          <PendingApprovalsWidget user={user} />
          
          {/* Third widget transforms */}
          {!isLoggedIn ? (
            <LoginWidget 
              loading={loginState === "verifying"}
              onSubmit={handleLoginSubmit}
            />
          ) : !outlookSkipped ? (
            <OutlookConnectorWidget
              onSkip={() => setOutlookSkipped(true)}
            />
          ) : (
            <ConnectLaterWidget />
          )}
        </div>
      </div>
      
      <SplashFooter
        isLoggedIn={isLoggedIn}
        onSkipToChat={handleSkipToChat}
      />
    </div>
  );
}
```

---

# PART XII — IMPLEMENTATION ORDER

## 29. Build Sequence

### Phase 1 — Theme System & Base (Week 1)
```
[ ] Implement three themes (Sky Blue, Dark, Abstract)
[ ] Theme switching in settings
[ ] CSS variables for all colors
[ ] Typography system (weights, sizes)
[ ] Apply theme to demo page
```

### Phase 2 — Unified Splash Layout (Week 1)
```
[ ] Transparent header with profile + utility icons
[ ] Three-column body (greeting | content | widgets)
[ ] Time-based greeting logic
[ ] Pills component
[ ] Trust indicators
[ ] Footer
[ ] Test all 3 themes
```

### Phase 3 — Widget System (Week 2)
```
[ ] Today's Insight widget
[ ] Pending Approvals widget
[ ] Demo data when logged out
[ ] Real data when logged in
[ ] Widget transitions
```

### Phase 4 — Login Widget (Week 2)
```
[ ] File ID input form
[ ] Verifying state (button text change)
[ ] Error handling
[ ] Wire to /auth/login endpoint
[ ] Test login success/failure
```

### Phase 5 — Login → Outlook Transition (Week 3)
```
[ ] Cross-fade animation (200ms)
[ ] Header avatar appearance
[ ] Greeting name addition
[ ] Widget data refresh
[ ] Skip button reveal
[ ] Test complete flow end-to-end
```

### Phase 6 — Polish (Week 3)
```
[ ] Mobile responsive
[ ] Arabic RTL support
[ ] Accessibility audit
[ ] Performance optimization
[ ] User testing
```

---

# PART XIII — DETAILED TYPOGRAPHY EXAMPLES

## 30. Per-Element Typography

```
ELEMENT: "Good Afternoon"
  Font: Inter (or system font stack)
  Size: 64px
  Weight: 200 (ExtraLight)
  Line height: 1.1
  Letter spacing: -1.5px
  Color: #ffffff (dark theme) / #1a2744 (light)

ELEMENT: "Super" (the name after greeting)
  Same font properties as "Good Afternoon"
  But appears on second line
  Same weight (200) — keeps elegant feel
  
ELEMENT: "What would you like to know today?"
  Font: Inter
  Size: 16px
  Weight: 400
  Color: rgba(255,255,255,0.7) / rgba(26,39,68,0.7)
  Margin-top: 24px from name

ELEMENT: Pill text "P&L"
  Font: Inter
  Size: 14px
  Weight: 500
  Color: inherit

ELEMENT: "TODAY'S INSIGHT"
  Font: Inter
  Size: 11px
  Weight: 600
  Letter spacing: 1.5px
  Transform: uppercase
  Color: rgba(255,255,255,0.5)

ELEMENT: "Revenue ↗ +12%"
  Font: Inter
  Size: 13px
  Weight: 500
  Color: #4ecdc4 (cyan/green)

ELEMENT: "AED 17.4M"
  Font: Inter
  Size: 40px
  Weight: 300 (Light)
  Letter spacing: -0.5px
  Font-variant-numeric: tabular-nums

ELEMENT: "Best month in Q1"
  Font: Inter
  Size: 13px
  Weight: 400
  Color: rgba(255,255,255,0.6)

ELEMENT: "Explore →" (CTA)
  Font: Inter
  Size: 14px
  Weight: 500
  Color: #c9a84c

ELEMENT: "Connect Outlook to unlock inbox insights."
  Font: Inter
  Size: 14px
  Weight: 400
  Style: italic
  Color: rgba(255,255,255,0.5)

ELEMENT: "✓ 247 queries today"
  Font: Inter
  Size: 13px
  Weight: 400
  Color: rgba(255,255,255,0.5)
  Checkmarks: #c9a84c (gold)

ELEMENT: "◊ Odoo Omni-Agent · Elrace" (footer)
  Font: Inter
  Size: 13px
  Weight: 400
  Color: rgba(255,255,255,0.6)
  Diamond: #c9a84c

ELEMENT: "Skip → Open Chat" button
  Font: Inter
  Size: 14px
  Weight: 500
  Color: #c9a84c (gold)
  Background: rgba(201,168,76,0.1)
  Border-radius: 100px
  Padding: 12px 24px
```

---

# PART XIV — KEY PRINCIPLES SUMMARY

## 31. The 10 Commandments of This Design

```
1. ONE SCREEN, TWO STATES
   Not logged in + Logged in = same layout, different content

2. HEADER IS TRANSPARENT
   No different contrast bar at top
   Floats over the body seamlessly

3. WIDGETS ALWAYS VISIBLE
   Even logged out, show insights/approvals
   Build trust before login

4. LOGIN IS A WIDGET
   Not a separate screen or modal
   Replaces Outlook widget in same position

5. SMOOTH STATE TRANSITIONS
   No page reload
   Cross-fade between login → outlook
   200ms only

6. SKY BLUE FOR LIGHT
   Not cream
   Daytime corporate feel

7. SMART TYPOGRAPHY
   ExtraLight for hero (200)
   Light for numbers (300)
   Regular for body (400)
   Medium for labels/buttons (500)
   SemiBold for section heads (600)
   Bold only when critical (700)

8. ITALIC FOR HINTS ONLY
   Not for headers
   Not for buttons
   For subtle suggestions

9. STATIC PREMIUM FEEL
   No motion except 200ms cross-fade
   Hover background only

10. CLEAN > FANCY
    Less is more
    Whitespace is luxury
    Glass effects, not gradients
```

---

# PART XV — TELL CURSOR

```
"Read SPLASH_SCREEN_PLAN_V2.md.

THIS REPLACES the original SPLASH_SCREEN_PLAN.md design.

Key changes:
1. ONE unified screen (not separate login + splash)
2. Header is TRANSPARENT (no different bar)
3. All widgets visible even when logged out
4. Login widget replaces Outlook widget in same position
5. After login: cross-fade (200ms) to Outlook widget
6. Light theme is SKY BLUE (not cream)
7. Greeting is ExtraLight 200 weight, 64px

Start Phase 1: Theme system & base
Start Phase 2: Unified splash layout

Reference:
- The two user screenshots for layout
- MAIN_SCREENS_LAYOUT_PLAN.md for what comes after splash

Critical rules:
- NO motion except 200ms login→outlook cross-fade
- Header transparent (NEVER different contrast)
- Same layout for logged out and logged in
- Smart typography weights (200/300/400/500/600/700)
- Italic only for hints, not headers"
```

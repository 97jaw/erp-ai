# VISUALIZE AGENT PLAN

> **Concept:** A dedicated second AI agent called **"Visualize"** with its own UI panel. Users drag responses from the main chat onto Visualize, choose output format (PDF / Excel / Dashboard), customize theme/columns/charts, and Visualize produces professional reports.

> **Strategic principle:** Separation of concerns — the main chat agent retrieves and analyzes data; the Visualize agent designs and formats outputs. Each agent specializes in what it does best.

> **Read first:** `PROJECT_CONTEXT.md`, `FINANCIAL_INTELLIGENCE_PLAN.md`, `V1.2_UI_LAYOUT.md`

---

# PART I — STRATEGIC VISION

## 1. Why a Separate Visualize Agent?

```
Current Architecture (Single Agent):
  Main Chat Agent does EVERYTHING:
    → Understands query
    → Fetches data
    → Analyzes
    → Formats output
    → Generates PDF
    → Designs visualizations

  Problems:
    ❌ Cognitive overload for one agent
    ❌ Hard to iterate on formatting (rebuilds everything)
    ❌ Cannot reuse data across multiple report formats
    ❌ Mixing analysis with presentation

New Architecture (Specialist Agents):
  Main Chat Agent: "What" — gets the data and analyzes
  Visualize Agent: "How" — formats and presents
  
  Benefits:
    ✓ Clean separation of concerns
    ✓ Reuse same data in multiple formats
    ✓ Iterate on report design without re-fetching
    ✓ Each agent has specialized prompts
    ✓ User controls the output explicitly
    ✓ Drag-and-drop is intuitive
```

## 2. The User Experience

```
1. User asks main chat: "Show me P&L for last quarter"
   → Main chat fetches data, shows summary with KPIs

2. User likes the data, wants a polished report
   → User DRAGS the response card onto Visualize panel
   → Visualize panel opens on LEFT side

3. Visualize Agent greets:
   "I see you want to visualize the P&L Q1 data.
    What would you like to create?"
   [📄 PDF Report] [📊 Excel] [📈 Dashboard]

4. User clicks [📄 PDF Report]
   → Visualize asks:
   "Great choice. Let me know your preferences:"
   - Theme: [Corporate Blue] [Elegant Gold] [Modern Dark] [Minimalist]
   - Layout: [Executive] [Detailed] [Comparative]
   - Include: [✓] Cover [✓] Charts [✓] Tables [✓] Insights [ ] Page numbers
   - Language: [English] [Arabic] [Both]

5. Visualize Agent builds the PDF
   → Shows live preview as it generates
   → User can refine: "Make the charts bigger"
   → Iterates until perfect

6. User downloads / shares the final report
```

---

# PART II — UI/UX DESIGN

## 3. Layout: The Three-Panel System

```
┌──────────────────────────────────────────────────────────────────┐
│                              HEADER                              │
├──────────┬─────────────────────────────────────────┬────────────┤
│          │                                         │            │
│ VISUALIZE│         MAIN CHAT AREA                  │  QUERY TABS │
│  PANEL   │                                         │   (history) │
│          │     [Chat messages]                     │            │
│ (left)   │     [Drag responses from here]          │  (right)   │
│          │                                         │            │
│  - Drop  │                                         │            │
│    Zone  │                                         │            │
│          │                                         │            │
│  - Build │                                         │            │
│    Area  │                                         │            │
│          │                                         │            │
│  - Tools │                                         │            │
└──────────┴─────────────────────────────────────────┴────────────┘

Toggle:
  Visualize panel: Cmd+V or click "Visualize" tab on left edge
  When closed: thin vertical strip with "Visualize" vertical text
```

## 4. Visualize Panel Layout (Detailed)

```
╔═══════════════════════════════════════════╗
║          ◊ VISUALIZE AGENT          [×]  ║
╠═══════════════════════════════════════════╣
║                                           ║
║  ┌─ DROP ZONE ──────────────────────┐    ║
║  │                                  │    ║
║  │   Drag a response here           │    ║
║  │   ┌─────┐  ┌─────┐               │    ║
║  │   │ P&L │  │Proj │  ← dropped    │    ║
║  │   └─────┘  └─────┘               │    ║
║  │                                  │    ║
║  └──────────────────────────────────┘    ║
║                                           ║
║  ┌─ AGENT CHAT ────────────────────┐    ║
║  │                                  │    ║
║  │ 🎨 I see your P&L data.          │    ║
║  │    What should I build?          │    ║
║  │                                  │    ║
║  │  [📄 PDF]  [📊 Excel] [📈 Dash]  │    ║
║  │                                  │    ║
║  │ User: "PDF, corporate theme"     │    ║
║  │                                  │    ║
║  │ 🎨 Perfect. Customize:           │    ║
║  │   Sections to include:           │    ║
║  │   [✓] Cover page                 │    ║
║  │   [✓] Executive summary          │    ║
║  │   [✓] KPI dashboard              │    ║
║  │   [✓] Income chart               │    ║
║  │   [✓] Expense breakdown          │    ║
║  │   [ ] Cash flow analysis         │    ║
║  │                                  │    ║
║  │   [Customize Theme]              │    ║
║  │   [Generate Report ►]            │    ║
║  │                                  │    ║
║  └──────────────────────────────────┘    ║
║                                           ║
║  ┌─ LIVE PREVIEW ──────────────────┐    ║
║  │                                  │    ║
║  │  [Thumbnail of PDF page 1]       │    ║
║  │  [Thumbnail of PDF page 2]       │    ║
║  │                                  │    ║
║  │  [Open Full Preview]             │    ║
║  │                                  │    ║
║  └──────────────────────────────────┘    ║
║                                           ║
║  ┌─ ACTIONS ───────────────────────┐    ║
║  │ [⬇ Download]                    │    ║
║  │ [📧 Email]                       │    ║
║  │ [🔗 Share Link]                  │    ║
║  │ [🔄 Refine]                      │    ║
║  └──────────────────────────────────┘    ║
║                                           ║
╚═══════════════════════════════════════════╝
```

## 5. Drag and Drop Mechanics

### 5.1 What Can Be Dragged

```
Draggable items from main chat:
  ✓ Response cards (entire AI response)
  ✓ Individual visualizations (KPI cards, charts, tables)
  ✓ Specific data sections
  ✓ Multiple responses (multi-select with Cmd+click)
```

### 5.2 Drag Visual Feedback

```
On hover over a response:
  → Subtle "drag handle" icon appears (top-right)
  → Cursor changes to grab on hover

On drag start:
  → Original card becomes semi-transparent
  → Floating "ghost" version follows cursor
  → Visualize panel auto-opens (if closed)
  → Drop zone glows with gold highlight

While dragging over Visualize:
  → Drop zone shows: "Drop to visualize ✦"
  → Pulsing animation
  → Other UI dimmed

On drop:
  → Card "lands" in drop zone with bounce
  → Confetti / sparkle effect
  → Soft "drop" sound
  → Visualize agent immediately responds
  → Main chat returns to normal opacity
```

### 5.3 Multiple Items Stacking

```
When user drags multiple items:
  ┌─ DROP ZONE ────────────────────┐
  │                                │
  │  ┌──┐                          │
  │  │1 │                          │
  │  └──┘  ┌──┐                    │
  │        │2 │   ┌──┐             │
  │        └──┘   │3 │             │
  │               └──┘             │
  │                                │
  │  3 items ready to visualize    │
  │  [Combine] [Clear] [Build →]   │
  └────────────────────────────────┘

User can:
  - Click "Combine" → merge into one report
  - Click individual item → focus on it
  - Drag to remove from drop zone
  - Reorder items
```

---

# PART III — VISUALIZE AGENT INTELLIGENCE

## 6. The Agent's System Prompt

```python
VISUALIZE_AGENT_PROMPT = """
You are "Visualize" — a specialized AI agent for transforming data 
into beautiful, professional reports.

Your role:
- Take data that the main chat has retrieved
- Help the user choose output format
- Customize the design based on user preferences
- Generate polished PDFs, Excel files, or dashboards
- Iterate based on user feedback

You DO NOT:
- Fetch new data (that's the main agent's job)
- Run analytics queries
- Answer questions about the underlying data
- Modify the source data

You DO:
- Design beautiful layouts
- Suggest theme/color combinations
- Recommend chart types
- Format tables professionally
- Generate iterations quickly

═══════════════════════════════════════════════════════════
INITIAL GREETING (when items dropped):
═══════════════════════════════════════════════════════════

Look at the data dropped:
- Single item: "I see your [report type] data. What would you like to create?"
- Multiple items: "I see [N] items. Should I combine them or work with each separately?"

Then ALWAYS offer the 3 output types:
[📄 PDF Report] [📊 Excel Spreadsheet] [📈 Dashboard]

═══════════════════════════════════════════════════════════
PDF GENERATION FLOW:
═══════════════════════════════════════════════════════════

After user picks PDF:

1. Ask about THEME first:
   "Which theme suits your audience?"
   - 🏢 Corporate Blue (formal, conservative)
   - ✨ Elegant Gold (premium, executive)
   - 🌙 Modern Dark (sleek, tech)
   - 📋 Minimalist (clean, simple)
   - 🎨 Custom (let me pick colors)

2. Ask about LAYOUT:
   "What layout style?"
   - Executive Summary (1-2 pages, KPIs focused)
   - Detailed Report (full breakdown, 5-10 pages)
   - Comparative (side-by-side periods)
   - Presentation Style (large fonts, less density)

3. Ask about SECTIONS to include (checkboxes):
   Based on the data, suggest sections:
   [✓] Cover Page
   [✓] Executive Summary
   [✓] KPI Dashboard
   [✓] Charts (Bar/Line/Pie)
   [✓] Data Tables
   [✓] Insights & Recommendations
   [ ] Appendix
   [ ] Glossary

4. Ask about additional options:
   - Include company logo? [Yes] [No]
   - Page numbers? [Yes] [No]
   - Watermark? [None / Confidential / Draft]
   - Language: [English] [Arabic] [Bilingual]

5. Generate and show preview
6. Accept refinements: "make it bigger", "change to dark", etc.

═══════════════════════════════════════════════════════════
EXCEL GENERATION FLOW:
═══════════════════════════════════════════════════════════

After user picks Excel:

1. Ask about STRUCTURE:
   "How should I organize the data?"
   - Single sheet (all data on one tab)
   - Multi-sheet (one tab per section)
   - Pivot-ready (with proper structure for pivot tables)

2. Ask about FORMATTING:
   - Apply theme colors? [Yes] [No]
   - Currency formatting (AED, comma-separated)? [Yes] [No]
   - Highlight negatives in red? [Yes] [No]
   - Add totals row? [Yes] [No]
   - Add charts on separate tab? [Yes] [No]

3. Ask about COLUMNS (which to include):
   Show all available columns as checkboxes
   User can reorder by dragging

4. Generate Excel file

═══════════════════════════════════════════════════════════
DASHBOARD GENERATION FLOW:
═══════════════════════════════════════════════════════════

(Coming in next plan - placeholder for now)
Acknowledge: "Dashboards are coming soon. Want PDF or Excel for now?"

═══════════════════════════════════════════════════════════
REFINEMENT HANDLING:
═══════════════════════════════════════════════════════════

User says "make the chart bigger":
  → Identify which chart
  → Adjust size in spec
  → Regenerate
  → Show new preview

User says "change to dark theme":
  → Switch theme
  → Regenerate
  → Keep all other choices

User says "remove the insights section":
  → Update section list
  → Regenerate

Always show before/after if helpful.
Always confirm changes were applied.

═══════════════════════════════════════════════════════════
TONE:
═══════════════════════════════════════════════════════════

- Friendly but professional
- Action-oriented
- Use chat-style language
- Use design vocabulary correctly
- Excited about creating beautiful outputs
- "I see..." "Let me..." "I'll..." 
"""
```

## 7. Visualize Agent Capabilities

```python
# tools/visualize_tools.py

VISUALIZE_TOOLS = [
    {
        "name": "generate_pdf",
        "description": "Generate a PDF report from data with customizations",
        "input_schema": {
            "type": "object",
            "properties": {
                "data_context": {"type": "object"},
                "theme": {"type": "string", "enum": [
                    "corporate_blue", "elegant_gold", "modern_dark",
                    "minimalist", "custom"
                ]},
                "layout": {"type": "string", "enum": [
                    "executive", "detailed", "comparative", "presentation"
                ]},
                "sections": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "options": {
                    "type": "object",
                    "properties": {
                        "include_logo": {"type": "boolean"},
                        "page_numbers": {"type": "boolean"},
                        "watermark": {"type": "string"},
                        "language": {"type": "string"}
                    }
                }
            }
        }
    },
    {
        "name": "generate_excel",
        "description": "Generate an Excel file from data",
        "input_schema": {
            "type": "object",
            "properties": {
                "data_context": {"type": "object"},
                "structure": {"type": "string", "enum": [
                    "single_sheet", "multi_sheet", "pivot_ready"
                ]},
                "formatting": {
                    "type": "object",
                    "properties": {
                        "theme_colors": {"type": "boolean"},
                        "currency_format": {"type": "boolean"},
                        "highlight_negatives": {"type": "boolean"},
                        "add_totals": {"type": "boolean"},
                        "include_charts": {"type": "boolean"}
                    }
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
    },
    {
        "name": "refine_output",
        "description": "Refine the last generated output based on user feedback",
        "input_schema": {
            "type": "object",
            "properties": {
                "output_id": {"type": "string"},
                "refinement_request": {"type": "string"}
            }
        }
    }
]
```

---

# PART IV — REPORT TEMPLATES & THEMES

## 8. PDF Theme Library

### 8.1 Theme 1: Corporate Blue

```python
THEME_CORPORATE_BLUE = {
    "name": "Corporate Blue",
    "description": "Formal, conservative — for boards and investors",
    
    "colors": {
        "primary": "#1a5490",      # Deep blue
        "secondary": "#4a90c2",    # Mid blue
        "accent": "#fbbf24",       # Gold accent
        "text_primary": "#1f2937",
        "text_secondary": "#6b7280",
        "background": "#ffffff",
        "table_header_bg": "#1a5490",
        "table_header_fg": "#ffffff",
        "table_row_alt": "#f3f4f6",
        "positive": "#059669",     # Green
        "negative": "#dc2626",     # Red
    },
    
    "fonts": {
        "header": "Georgia, serif",
        "body": "Calibri, Arial, sans-serif",
        "numbers": "Calibri, monospace",
    },
    
    "spacing": {
        "section_gap": 32,
        "table_padding": 12,
    },
}
```

### 8.2 Theme 2: Elegant Gold

```python
THEME_ELEGANT_GOLD = {
    "name": "Elegant Gold",
    "description": "Premium, executive — for high-end presentations",
    
    "colors": {
        "primary": "#1a2744",      # Deep navy
        "secondary": "#c9a84c",    # UAE gold
        "accent": "#a8873d",       # Darker gold
        "text_primary": "#1a2744",
        "text_secondary": "#5a6378",
        "background": "#fefdfb",
        "table_header_bg": "#1a2744",
        "table_header_fg": "#c9a84c",
        "table_row_alt": "#faf7f0",
        "positive": "#10b981",
        "negative": "#ef4444",
    },
    
    "fonts": {
        "header": "Playfair Display, serif",
        "body": "Inter, sans-serif",
        "numbers": "Inter, monospace",
    },
}
```

### 8.3 Theme 3: Modern Dark

```python
THEME_MODERN_DARK = {
    "name": "Modern Dark",
    "description": "Sleek, tech — for digital-first audiences",
    
    "colors": {
        "primary": "#0a0f1e",      # Deep dark
        "secondary": "#4ecdc4",    # Cyan
        "accent": "#c9a84c",       # Gold
        "text_primary": "#e8eaf6",
        "text_secondary": "#9ca3af",
        "background": "#0d1428",
        "table_header_bg": "#1a2744",
        "table_header_fg": "#4ecdc4",
        "table_row_alt": "#141b2e",
        "positive": "#4ecdc4",
        "negative": "#ff6b6b",
    },
    
    "fonts": {
        "header": "Inter, sans-serif",
        "body": "Inter, sans-serif",
        "numbers": "Inter, monospace",
    },
}
```

### 8.4 Theme 4: Minimalist

```python
THEME_MINIMALIST = {
    "name": "Minimalist",
    "description": "Clean, simple — let the data speak",
    
    "colors": {
        "primary": "#000000",
        "secondary": "#525252",
        "accent": "#000000",
        "text_primary": "#000000",
        "text_secondary": "#737373",
        "background": "#ffffff",
        "table_header_bg": "#ffffff",
        "table_header_fg": "#000000",
        "table_row_alt": "#fafafa",
        "positive": "#000000",
        "negative": "#000000",  # All black, no color
    },
    
    "fonts": {
        "header": "Helvetica Neue, sans-serif",
        "body": "Helvetica Neue, sans-serif",
        "numbers": "Helvetica Neue, monospace",
    },
}
```

## 9. PDF Layout Templates

### 9.1 Executive Layout (Inspired by Image 1)

```
Structure for "executive" layout:
  Page 1: Cover + KPI Dashboard

  ┌────────────────────────────────┐
  │  [LOGO]   Profit & Loss        │
  │           Statement            │
  │           April 2026           │
  ├────────────────────────────────┤
  │                                │
  │  KPI GRID (4 large boxes)      │
  │  ┌──────┐ ┌──────┐             │
  │  │Income│ │Profit│             │
  │  └──────┘ └──────┘             │
  │  ┌──────┐ ┌──────┐             │
  │  │Exp.  │ │Margin│             │
  │  └──────┘ └──────┘             │
  │                                │
  │  YEAR TREND CHART              │
  │  ┌────────────────────────┐    │
  │  │ [Line chart]           │    │
  │  │                        │    │
  │  └────────────────────────┘    │
  │                                │
  │  TOP EXPENSES (mini chart)     │
  │  ▓▓▓▓▓▓ Wages           35%    │
  │  ▓▓▓▓   Marketing       12%    │
  │  ▓▓▓    Rent             8%    │
  │                                │
  └────────────────────────────────┘
```

### 9.2 Detailed Layout (Inspired by Image 4)

```
Multi-page detailed report:

Page 1: Cover
Page 2: Executive Summary + KPIs
Page 3: Revenue Breakdown
        ├─ By client
        ├─ By project  
        └─ Trend chart
Page 4: Expense Breakdown
        ├─ Operating expenses (table)
        ├─ Non-recurring (table)
        └─ Top 10 chart
Page 5: Profit Analysis
        ├─ Gross profit walk
        ├─ Operating profit
        └─ Net profit
Page 6: Cash Flow
Page 7: Comparative (vs previous period)
Page 8: Insights & Recommendations
Page 9: Appendix (raw data)
```

### 9.3 Comparative Layout (Inspired by Image 2)

```
Side-by-side period comparison:

  ┌────────────────────────────────────────────┐
  │  INCOME DETAILS    Q1    Q2    Q3    Q4   │
  │  ──────────────────────────────────────────│
  │  Sales Revenue     $23K  $25K  $19K  $19K │
  │  Cost of Sales     $14K  $16K  $14K  $16K │
  │  Gross Profit     $8.5K $9.0K $5.0K $3.0K │
  │                                            │
  │  Operating Exp.    $8K   $7K   $8K   $8.5K│
  │  Net Profit       $1.3K $4.1K -$1.5K -$3K │
  └────────────────────────────────────────────┘

  All periods visible at once
  Useful for trend analysis
  Negative values in red
```

## 10. Excel Templates

### 10.1 Single Sheet Layout

```
Inspired by Image 2 (database view):

Sheet: "Financial Data"
  
  Row 1: Headers (frozen, formatted)
  Row 2-N: Data rows
  Last row: Totals (formatted bold, colored)

Formatting:
  - Currency: AED #,##0
  - Headers: white text on navy background
  - Alternating row colors (subtle gray)
  - Negative numbers in red
  - Totals row: gold background, bold
  - Auto-width columns
  - Freeze top row + first column
  - Filter dropdown on each column
```

### 10.2 Multi-Sheet Layout

```
Sheet 1: Summary
  ├─ KPI grid at top
  ├─ Main chart
  └─ Quick stats

Sheet 2: Revenue
  ├─ By client
  ├─ By project
  └─ Monthly breakdown

Sheet 3: Expenses
  ├─ Operating
  ├─ Non-recurring
  └─ Category breakdown

Sheet 4: Charts
  ├─ All visualizations
  └─ Comparison charts

Sheet 5: Raw Data
  ├─ Source records
  └─ For deep analysis

Each sheet has:
  - Branded header
  - Navigation back to Summary
  - Consistent formatting
```

### 10.3 Pivot-Ready Layout

```
Sheet 1: Data (flat, normalized)
  Columns: Date | Account | Partner | Project | Amount | Type

Sheet 2: Pivot
  Pre-built pivot table
  Slicers for: Date, Project, Type
  Charts auto-update with slicers

User can drag fields to customize
```

---

# PART V — IMPLEMENTATION ARCHITECTURE

## 11. Backend Architecture

### 11.1 Separate API Endpoints

```
/visualize/start              POST  Initialize Visualize session
/visualize/chat               POST  Chat with Visualize agent
/visualize/chat/stream        POST  SSE stream
/visualize/generate-pdf       POST  Generate PDF (with full spec)
/visualize/generate-excel     POST  Generate Excel file
/visualize/preview/:id        GET   Get preview image
/visualize/download/:id       GET   Download generated file
/visualize/refine             POST  Apply refinement
/visualize/sessions/:id       GET   Get session state
```

### 11.2 Agent Routing

```python
# gateway/main.py

class VisualizeContext:
    """State for a Visualize agent session."""
    def __init__(self, session_id: str, user_id: int):
        self.session_id = session_id
        self.user_id = user_id
        self.dropped_items = []  # Data from main chat
        self.output_type = None  # 'pdf', 'excel', 'dashboard'
        self.theme = None
        self.layout = None
        self.sections = []
        self.options = {}
        self.current_output_id = None
        self.history = []  # Refinement history


@app.post("/visualize/start")
async def visualize_start(
    request: VisualizeStartRequest,
    user: User = Depends(get_current_user),
):
    """Initialize a Visualize session with dropped data."""
    session = VisualizeContext(
        session_id=str(uuid.uuid4()),
        user_id=user.id,
    )
    
    # Store dropped data
    session.dropped_items = request.items
    
    # Save to Redis for fast access
    await redis.setex(
        f"visualize:{session.session_id}",
        3600,  # 1 hour
        json.dumps(session.to_dict()),
    )
    
    return {"session_id": session.session_id}


@app.post("/visualize/chat/stream")
async def visualize_chat_stream(
    request: VisualizeChatRequest,
    user: User = Depends(get_current_user),
):
    """Stream chat with Visualize agent."""
    session = await load_visualize_session(request.session_id)
    
    # Build context-aware messages
    messages = build_visualize_context(session, request.message)
    
    # Use Claude with Visualize prompt
    async def generate():
        with client.messages.stream(
            model=MODEL,
            max_tokens=2048,
            system=VISUALIZE_AGENT_PROMPT,
            tools=VISUALIZE_TOOLS,
            messages=messages,
        ) as stream:
            for event in stream:
                # Process events
                yield f"data: {json.dumps(event_data)}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 11.3 PDF Generation Pipeline

```python
# visualize/pdf_generator.py

from jinja2 import Template
from weasyprint import HTML, CSS
import matplotlib.pyplot as plt
import io
import base64

class PDFGenerator:
    """Generates PDFs from visualization spec."""
    
    def __init__(self, theme_name: str = "corporate_blue"):
        self.theme = THEMES[theme_name]
        self.template_dir = "visualize/templates"
    
    def generate(self, spec: dict) -> str:
        """
        Generate PDF from full specification.
        Returns path to generated PDF.
        """
        # 1. Process each section
        rendered_sections = []
        for section in spec["sections"]:
            html = self.render_section(section)
            rendered_sections.append(html)
        
        # 2. Build complete HTML
        template = self.load_template(spec.get("layout", "executive"))
        full_html = template.render(
            title=spec["title"],
            subtitle=spec.get("subtitle"),
            sections=rendered_sections,
            theme=self.theme,
            company_logo_url=spec.get("logo_url"),
            language=spec.get("language", "en"),
            is_rtl=(spec.get("language") == "ar"),
            include_page_numbers=spec.get("page_numbers", True),
            watermark=spec.get("watermark"),
        )
        
        # 3. Render to PDF
        output_id = str(uuid.uuid4())
        pdf_path = f"/reports/{output_id}.pdf"
        
        HTML(string=full_html).write_pdf(
            pdf_path,
            stylesheets=[CSS(string=self.get_theme_css())],
        )
        
        # 4. Generate preview thumbnail
        self.generate_preview(pdf_path, output_id)
        
        return {
            "output_id": output_id,
            "pdf_url": f"/visualize/download/{output_id}",
            "preview_url": f"/visualize/preview/{output_id}",
        }
    
    def render_section(self, section: dict) -> str:
        """Render individual section based on type."""
        section_type = section["type"]
        
        renderers = {
            "cover": self.render_cover,
            "executive_summary": self.render_executive_summary,
            "kpi_grid": self.render_kpi_grid,
            "chart": self.render_chart,
            "table": self.render_table,
            "comparative_table": self.render_comparative_table,
            "insights": self.render_insights,
            "appendix": self.render_appendix,
        }
        
        renderer = renderers.get(section_type)
        if not renderer:
            return ""
        
        return renderer(section)
    
    def render_chart(self, section: dict) -> str:
        """Render chart as PNG and embed."""
        chart_type = section.get("chart_type", "bar")
        
        if chart_type == "bar":
            return self.render_bar_chart(section)
        elif chart_type == "line":
            return self.render_line_chart(section)
        elif chart_type == "pie":
            return self.render_pie_chart(section)
    
    def render_bar_chart(self, section: dict) -> str:
        """Use matplotlib to render high-quality chart."""
        plt.figure(figsize=(10, 5), dpi=300)
        
        labels = section["data"]["labels"]
        values = section["data"]["values"]
        
        bars = plt.bar(labels, values, color=self.theme["colors"]["secondary"])
        plt.title(section["title"], fontsize=14)
        plt.ylabel("Amount (AED)")
        plt.xticks(rotation=30)
        plt.tight_layout()
        
        # Save to base64
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=300, bbox_inches="tight")
        plt.close()
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        
        return f"""
        <div class="chart-section">
            <h3>{section["title"]}</h3>
            <img src="data:image/png;base64,{img_b64}" alt="Chart">
        </div>
        """
```

### 11.4 Excel Generation Pipeline

```python
# visualize/excel_generator.py

import xlsxwriter
from io import BytesIO

class ExcelGenerator:
    """Generates Excel files with full formatting."""
    
    def __init__(self, theme_name: str = "corporate_blue"):
        self.theme = THEMES[theme_name]
    
    def generate(self, spec: dict) -> dict:
        """Generate Excel file from spec."""
        output_id = str(uuid.uuid4())
        excel_path = f"/reports/{output_id}.xlsx"
        
        workbook = xlsxwriter.Workbook(excel_path)
        
        # Define theme-based formats
        formats = self.create_formats(workbook)
        
        # Generate based on structure
        if spec["structure"] == "single_sheet":
            self.generate_single_sheet(workbook, formats, spec)
        elif spec["structure"] == "multi_sheet":
            self.generate_multi_sheet(workbook, formats, spec)
        elif spec["structure"] == "pivot_ready":
            self.generate_pivot_ready(workbook, formats, spec)
        
        workbook.close()
        
        return {
            "output_id": output_id,
            "excel_url": f"/visualize/download/{output_id}",
        }
    
    def create_formats(self, workbook):
        """Theme-aware cell formats."""
        return {
            "header": workbook.add_format({
                "bold": True,
                "bg_color": self.theme["colors"]["table_header_bg"],
                "font_color": self.theme["colors"]["table_header_fg"],
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }),
            "currency": workbook.add_format({
                "num_format": '"AED" #,##0',
                "align": "right",
            }),
            "currency_negative": workbook.add_format({
                "num_format": '"AED" #,##0;[Red]"AED" -#,##0',
                "align": "right",
            }),
            "percent": workbook.add_format({
                "num_format": "0.00%",
                "align": "right",
            }),
            "total_row": workbook.add_format({
                "bold": True,
                "bg_color": self.theme["colors"]["accent"],
                "top": 2,
                "num_format": '"AED" #,##0',
            }),
            "section_header": workbook.add_format({
                "bold": True,
                "font_size": 14,
                "bg_color": self.theme["colors"]["primary"],
                "font_color": "white",
            }),
        }
    
    def generate_single_sheet(self, workbook, formats, spec):
        """All data on one sheet with proper formatting."""
        sheet = workbook.add_worksheet("Financial Data")
        
        # Title row
        sheet.merge_range("A1:F1", spec["title"],
                         formats["section_header"])
        sheet.set_row(0, 30)
        
        # Headers
        headers = spec["columns"]
        for col, header in enumerate(headers):
            sheet.write(2, col, header, formats["header"])
        
        # Data rows
        data = spec["data_context"]["rows"]
        for row_idx, row_data in enumerate(data, start=3):
            for col_idx, value in enumerate(row_data):
                fmt = formats["currency_negative"] if isinstance(value, (int, float)) else None
                sheet.write(row_idx, col_idx, value, fmt)
        
        # Totals row
        total_row = len(data) + 3
        sheet.write(total_row, 0, "TOTAL", formats["header"])
        for col_idx in range(1, len(headers)):
            col_letter = chr(65 + col_idx)
            formula = f"=SUM({col_letter}4:{col_letter}{total_row})"
            sheet.write_formula(total_row, col_idx, formula, formats["total_row"])
        
        # Auto-width
        for col_idx in range(len(headers)):
            sheet.set_column(col_idx, col_idx, 18)
        
        # Freeze
        sheet.freeze_panes(3, 0)
        
        # Filter
        sheet.autofilter(2, 0, len(data) + 2, len(headers) - 1)
        
        # Add chart if requested
        if spec.get("formatting", {}).get("include_charts"):
            self.add_chart_sheet(workbook, spec, data)
```

---

# PART VI — FRONTEND IMPLEMENTATION

## 12. React Components Structure

```
ooa-ui/src/visualize/
├── VisualizePanel.jsx          # Main panel container
├── DropZone.jsx                # Drag-drop area
├── DroppedItem.jsx             # Visual of dropped item
├── VisualizeAgent.jsx          # Chat with Visualize agent
├── OutputTypePicker.jsx        # PDF/Excel/Dashboard chooser
├── ThemePicker.jsx             # Theme selection UI
├── LayoutPicker.jsx            # Layout chooser
├── SectionsBuilder.jsx         # Checkbox list of sections
├── LivePreview.jsx             # PDF/Excel preview
├── RefinementInput.jsx         # Iteration input
└── ActionsBar.jsx              # Download/Email/Share buttons
```

## 13. Drag-Drop Implementation

```jsx
// MainChatMessage.jsx — Make responses draggable

function ChatMessage({ msg }) {
  const handleDragStart = (e) => {
    e.dataTransfer.setData(
      "application/json",
      JSON.stringify({
        type: "chat_response",
        message_id: msg.id,
        text: msg.text,
        visualization: msg.visualization,
        timestamp: msg.created_at,
      })
    );
    e.dataTransfer.effectAllowed = "copy";
    
    // Visual feedback
    e.currentTarget.style.opacity = "0.5";
    
    // Auto-open Visualize panel
    document.dispatchEvent(new CustomEvent("open-visualize"));
  };
  
  const handleDragEnd = (e) => {
    e.currentTarget.style.opacity = "1";
  };
  
  return (
    <div
      draggable
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      className="chat-message"
    >
      {/* Existing message content */}
      <div className="drag-handle">
        <DragIcon /> {/* Visual hint */}
      </div>
      
      {msg.text}
      {msg.visualization && <Visualization viz={msg.visualization} />}
    </div>
  );
}


// VisualizePanel.jsx — Drop target

function VisualizePanel({ isOpen, onClose }) {
  const [droppedItems, setDroppedItems] = useState([]);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  
  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    setIsDraggingOver(true);
  };
  
  const handleDragLeave = () => {
    setIsDraggingOver(false);
  };
  
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDraggingOver(false);
    
    try {
      const data = JSON.parse(e.dataTransfer.getData("application/json"));
      
      // Add to dropped items
      setDroppedItems(prev => [...prev, data]);
      
      // Initialize Visualize session if first item
      if (droppedItems.length === 0) {
        initializeSession([...droppedItems, data]);
      }
      
      // Play drop sound
      sound.play("drop");
      
      // Animation feedback
      animateDropSuccess();
    } catch (err) {
      console.error("Drop failed:", err);
    }
  };
  
  if (!isOpen) {
    return <CollapsedStrip onClick={() => onClose(false)} />;
  }
  
  return (
    <div className="visualize-panel">
      <header>
        <h2>◊ Visualize</h2>
        <button onClick={onClose}>×</button>
      </header>
      
      <DropZone
        items={droppedItems}
        isDraggingOver={isDraggingOver}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onRemoveItem={(idx) => {
          setDroppedItems(prev => prev.filter((_, i) => i !== idx));
        }}
      />
      
      {droppedItems.length > 0 && (
        <>
          <VisualizeAgent
            sessionId={sessionId}
            droppedItems={droppedItems}
          />
          <LivePreview outputId={currentOutputId} />
          <ActionsBar outputId={currentOutputId} />
        </>
      )}
    </div>
  );
}
```

## 14. Visualize Agent Chat

```jsx
// VisualizeAgent.jsx

function VisualizeAgent({ sessionId, droppedItems }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  
  // Initial greeting based on dropped items
  useEffect(() => {
    if (droppedItems.length > 0 && messages.length === 0) {
      const greeting = generateInitialGreeting(droppedItems);
      setMessages([{
        id: "init",
        role: "agent",
        text: greeting,
        actions: [
          { type: "button", label: "📄 PDF", value: "pdf" },
          { type: "button", label: "📊 Excel", value: "excel" },
          { type: "button", label: "📈 Dashboard (Coming Soon)", value: "dashboard", disabled: true },
        ],
      }]);
    }
  }, [droppedItems]);
  
  const sendToVisualize = async (message) => {
    setLoading(true);
    
    try {
      const res = await fetch("/visualize/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message,
          dropped_items: droppedItems,
        }),
      });
      
      // Process SSE stream similar to main chat
      // ...
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };
  
  const handleActionClick = (action) => {
    sendToVisualize(`I want ${action.label}`);
  };
  
  return (
    <div className="visualize-chat">
      {messages.map(msg => (
        <div key={msg.id} className={`msg msg-${msg.role}`}>
          <div className="msg-text">{msg.text}</div>
          
          {/* Render interactive options if any */}
          {msg.actions && (
            <div className="msg-actions">
              {msg.actions.map(action => {
                if (action.type === "button") {
                  return (
                    <button
                      key={action.value}
                      disabled={action.disabled}
                      onClick={() => handleActionClick(action)}
                    >
                      {action.label}
                    </button>
                  );
                }
                if (action.type === "checkbox_list") {
                  return <CheckboxList items={action.items} />;
                }
                if (action.type === "theme_picker") {
                  return <ThemePicker themes={action.themes} />;
                }
                if (action.type === "color_picker") {
                  return <ColorPicker />;
                }
              })}
            </div>
          )}
        </div>
      ))}
      
      {loading && <ThinkingDots />}
      
      <div className="input-area">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && sendToVisualize(input)}
          placeholder="Tell Visualize what you want..."
        />
        <button onClick={() => sendToVisualize(input)}>→</button>
      </div>
    </div>
  );
}
```

## 15. Live Preview Component

```jsx
// LivePreview.jsx

function LivePreview({ outputId, outputType }) {
  const [previewUrl, setPreviewUrl] = useState(null);
  const [pages, setPages] = useState([]);
  
  useEffect(() => {
    if (!outputId) return;
    
    // Fetch preview thumbnails
    fetch(`/visualize/preview/${outputId}`)
      .then(r => r.json())
      .then(data => {
        setPages(data.pages); // Array of thumbnail URLs
      });
  }, [outputId]);
  
  if (!outputId) {
    return (
      <div className="preview-empty">
        Your preview will appear here
      </div>
    );
  }
  
  return (
    <div className="live-preview">
      <h3>Preview</h3>
      
      {outputType === "pdf" && (
        <div className="pdf-pages">
          {pages.map((url, i) => (
            <img
              key={i}
              src={url}
              alt={`Page ${i + 1}`}
              onClick={() => openFullPreview(outputId, i)}
            />
          ))}
        </div>
      )}
      
      {outputType === "excel" && (
        <div className="excel-preview">
          <ExcelTablePreview outputId={outputId} />
        </div>
      )}
      
      <button onClick={() => openFullPreview(outputId)}>
        View Full Preview
      </button>
    </div>
  );
}
```

---

# PART VII — IMPLEMENTATION PHASES

## 16. Build Order (8 Weeks)

### Phase 1 — Foundation & Drag-Drop (Week 1)
```
[ ] Build VisualizePanel component shell
[ ] Add toggle button / collapsed strip
[ ] Implement drag handlers on ChatMessage
[ ] Implement drop zone with visual feedback
[ ] Store dropped items in state
[ ] Add subtle animations and sounds
[ ] Test on desktop browsers
```

### Phase 2 — Visualize Agent (Week 2)
```
[ ] Create VISUALIZE_AGENT_PROMPT
[ ] Build /visualize/start endpoint
[ ] Build /visualize/chat/stream endpoint
[ ] Implement VisualizeAgent React component
[ ] Wire up streaming chat
[ ] Test agent greets correctly
[ ] Test agent asks right questions
```

### Phase 3 — PDF Themes (Week 3)
```
[ ] Implement 4 theme definitions
[ ] Build HTML templates per theme
[ ] Create section renderers (cover, KPI, chart, table)
[ ] Test PDF generation with each theme
[ ] Add theme picker UI
[ ] Match samples from images 1, 2, 3, 4
```

### Phase 4 — PDF Generation (Week 4)
```
[ ] Install WeasyPrint + Matplotlib
[ ] Build PDFGenerator class
[ ] Implement chart embedding (PNG)
[ ] Add company logo support
[ ] Add page numbering
[ ] Add watermark option
[ ] Test with real data
[ ] Verify file quality
```

### Phase 5 — Excel Generation (Week 5)
```
[ ] Install xlsxwriter
[ ] Build ExcelGenerator class
[ ] Theme-aware formatting
[ ] Single sheet template
[ ] Multi-sheet template
[ ] Pivot-ready template
[ ] Chart embedding in Excel
[ ] Test with real data
```

### Phase 6 — Live Preview (Week 6)
```
[ ] PDF to image conversion (PyMuPDF or pdf2image)
[ ] Excel to HTML preview
[ ] Thumbnail generation
[ ] Preview component
[ ] Click thumbnail to zoom
[ ] Full preview modal
```

### Phase 7 — Refinement Engine (Week 7)
```
[ ] Parse refinement requests
[ ] Update spec based on feedback
[ ] Regenerate output
[ ] Diff old vs new preview
[ ] Test 20+ refinement scenarios
```

### Phase 8 — Polish (Week 8)
```
[ ] Animations and transitions
[ ] Sound effects on drop, generate, download
[ ] Bilingual support (Arabic templates)
[ ] Mobile responsive
[ ] Error handling
[ ] Performance optimization
[ ] User testing
```

---

# PART VIII — QUALITY EXAMPLES

## 17. Expected Output Quality

### 17.1 PDF Quality Bar (Inspired by Image 4)

```
✓ Company name and address in header
✓ Date created / date issued
✓ Color-coded section dividers
✓ Three-column comparison support
✓ Subtotals and totals clearly highlighted
✓ Currency properly formatted ($x,xxx.xx or AED x,xxx)
✓ Negative numbers in red
✓ Clean typography
✓ Professional spacing
✓ Print-ready (proper margins)
```

### 17.2 Excel Quality Bar (Inspired by Image 2)

```
✓ Frozen header rows
✓ Frozen first column
✓ Alternating row colors
✓ Currency formatting throughout
✓ Negative numbers in red
✓ Bold totals row with background
✓ Auto-filter on columns
✓ Auto-width columns
✓ Multiple sheets with navigation
✓ Charts on separate tab
```

### 17.3 Dashboard Quality Bar (Inspired by Image 1)

```
(Coming in next plan)
✓ KPI cards with trends
✓ Year overview chart
✓ Monthly drill-down
✓ Top expenses with bars
✓ Color-coded indicators
✓ Interactive filters
```

---

# PART IX — INTEGRATION WITH MAIN CHAT

## 18. Connection Points

### 18.1 Sharing Data

```
Main chat fetches data → Visualize uses it
  ↓
No re-fetching needed for visualizations
  ↓
Visualize specs persisted per session
  ↓
User can return to chat and drag more items
```

### 18.2 Returning to Chat

```
After generating output:
  Visualize agent says:
  "Your PDF is ready! Want to:"
  [Download] [Email it] [Make changes] [Return to chat]
  
User clicks [Return to chat]:
  → Visualize panel collapses (not closes)
  → Main chat resumes
  → Notification: "Visualize has your file ready"
```

### 18.3 Cross-Agent References

```
Main chat: "Show me Q1 revenue"
[shows data]

User drags to Visualize, makes PDF report

Later in main chat:
User: "Compare with my last PDF"
Main chat agent: "I see you made a Q1 Revenue report on May 14.
                  Comparing current data with that report..."
```

---

# PART X — TELL CURSOR

```
"Read VISUALIZE_AGENT_PLAN.md.

Start Phase 1: Build the drag-and-drop foundation.

Implementation order:
1. Add VisualizePanel React component
2. Add toggle button (left edge of screen)
3. Make ChatMessage draggable (add drag handlers)
4. Implement drop zone with visual feedback
5. Store dropped items in state
6. Test drag-drop end to end

Reference:
- V1.2_UI_LAYOUT.md for panel layout patterns
- PRODUCT_QUALITY_FRAMEWORK.md for quality standards
- FINANCIAL_INTELLIGENCE_PLAN.md for data structures

After Phase 1 confirmed working, move to Phase 2 (Visualize Agent backend).

Note: This is a SEPARATE agent with its own prompt and tools.
Do NOT mix this with the main chat agent code.
Keep clean separation in code organization."
```

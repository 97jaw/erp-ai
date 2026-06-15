import {
  detectTextDirection,
  formatDateRangeBadge,
  hasRenderableVisualization,
  humanizeOutput,
  resolveVisualizationLevel,
  stripVisualization,
} from "./chat";

describe("stripVisualization", () => {
  it("removes visualization blocks", () => {
    const input = 'Summary\n<visualization>{"visual_type":"BAR_CHART"}</visualization>\nDone';
    expect(stripVisualization(input)).toBe("Summary\nDone");
  });

  it("truncates trailing partial visualization JSON", () => {
    const input = 'Hello\n{"visual_type":"BAR_CHART","data":{';
    expect(stripVisualization(input)).toBe("Hello");
  });
});

describe("humanizeOutput", () => {
  it("removes aggregate suffixes and Odoo tuples", () => {
    const input = "amount_total:sum: 0 for partner_id[54, 'Abu Dhabi Police']";
    expect(humanizeOutput(input)).toBe("amount_total: 0 for Abu Dhabi Police");
  });
});

describe("detectTextDirection", () => {
  it("detects rtl for Arabic-heavy paragraphs", () => {
    expect(detectTextDirection("مرحبا بالعالم")).toBe("rtl");
    expect(detectTextDirection("Hello world")).toBe("ltr");
  });
});

describe("formatDateRangeBadge", () => {
  it("formats a date range label", () => {
    const label = formatDateRangeBadge("2026-01-01", "2026-03-31", { defaulted: true });
    expect(label).toContain("default period");
  });
});

describe("resolveVisualizationLevel", () => {
  it("keeps summary tables hidden until expanded", () => {
    const viz = {
      visual_type: "FINANCIAL_REPORT",
      level: "summary",
      can_expand: true,
      total_records: 3,
      kpis: { total_income: 1, total_expense: 1, net_profit: 0, margin: 0 },
      data: {
        detail_table: { headers: ["Account"], rows: [["A", 1], ["B", 2], ["C", 3]] },
        all_rows: [["A", 1], ["B", 2], ["C", 3]],
      },
    };
    const summary = resolveVisualizationLevel(viz, "summary");
    expect(summary.data.rows).toEqual([]);
    const standard = resolveVisualizationLevel(viz, "standard");
    expect(standard.data.rows).toHaveLength(3);
  });
});

describe("hasRenderableVisualization", () => {
  it("accepts bar chart dict rows", () => {
    const viz = {
      visual_type: "BAR_CHART",
      data: {
        rows: [{ label: "Labor", value: 100 }, { label: "Materials", value: 200 }],
      },
    };
    expect(hasRenderableVisualization(viz)).toBe(true);
  });

  it("accepts project expense summary viz", () => {
    const viz = {
      visual_type: "PROJECT_EXPENSE_SUMMARY",
      kpis: {
        wo_amount: { value: 1000, label: "W.O Amount", unit: "AED" },
      },
    };
    expect(hasRenderableVisualization(viz)).toBe(true);
  });

  it("accepts project expense comparison viz", () => {
    const viz = {
      visual_type: "PROJECT_EXPENSE_COMPARISON",
      projects: [
        { id: 1, name: "A", total_expenses: 100 },
        { id: 2, name: "B", total_expenses: 200 },
      ],
    };
    expect(hasRenderableVisualization(viz)).toBe(true);
  });

  it("accepts file list viz with download rows", () => {
    const viz = {
      visual_type: "FILE_LIST",
      label: "Al Hili Healthcare Center — documents",
      data: {
        files: [
          {
            name: "W.O AHS-C-21-2016-506.pdf",
            mimetype: "application/pdf",
            download_token: "tok-1",
          },
        ],
      },
    };
    expect(hasRenderableVisualization(viz)).toBe(true);
  });
});

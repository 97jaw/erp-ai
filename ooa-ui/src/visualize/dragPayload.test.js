import {
  buildVisualizeDragPayload,
  isDuplicateDrop,
  labelForDroppedItem,
  parseVisualizeDragPayload,
} from "./dragPayload";

describe("visualize dragPayload", () => {
  it("round-trips a chat response payload", () => {
    const payload = buildVisualizeDragPayload({
      queryId: 42,
      messageId: "42-bot",
      question: "P&L this month",
      text: "Revenue is up",
      vizType: "KPI_CARD",
    });
    const parsed = parseVisualizeDragPayload(JSON.stringify(payload));
    expect(parsed).toEqual(payload);
  });

  it("labels from question text", () => {
    const label = labelForDroppedItem({
      question: "Show profit and loss this month",
      text: "",
    });
    expect(label).toContain("profit");
  });

  it("detects duplicate drops", () => {
    const item = buildVisualizeDragPayload({ queryId: 1, messageId: "1-bot" });
    expect(isDuplicateDrop([item], item)).toBe(true);
  });
});

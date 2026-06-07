import InsightWidget from "./widgets/InsightWidget";
import PendingWidget from "./widgets/PendingWidget";

export default function WidgetStack({
  insight,
  pending,
  revealWidgets,
  awaitingReveal = false,
  onInsightExplore,
  onPendingReview,
}) {
  const awaitClass = awaitingReveal ? "splash-await-reveal" : "";

  return (
    <aside
      className={`splash-right splash-right--live${revealWidgets ? " splash-right--revealed" : ""}`}
      aria-label="Your workspace"
    >
      <InsightWidget
        className={revealWidgets ? "splash-pop-in splash-pop-in--delay-4" : awaitClass}
        data={insight}
        onExplore={onInsightExplore}
      />
      <PendingWidget
        className={revealWidgets ? "splash-pop-in splash-pop-in--delay-5" : awaitClass}
        count={pending?.count}
        subtitle={pending?.subtitle}
        onReview={onPendingReview}
      />
    </aside>
  );
}

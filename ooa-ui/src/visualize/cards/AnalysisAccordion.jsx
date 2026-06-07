import AlternativesCard from "./AlternativesCard";
import CollapsibleSection from "./CollapsibleSection";
import InsightsCard from "./InsightsCard";
import InspectionCard from "./InspectionCard";

export default function AnalysisAccordion({
  brain,
  loading,
  onAlternativeSelect,
}) {
  const {
    inspection,
    findings,
    recommendation,
    isInspecting,
    isAnalyzing,
    isReady,
    showAlternatives,
    error,
  } = brain;

  const inspectionSubtitle = inspection?.date_range
    ? inspection.date_range
    : inspection?.row_count
      ? `${inspection.row_count} records`
      : null;

  const findingsBadge = findings.length ? `${findings.length}` : null;

  return (
    <div className="viz-analysis-accordion" aria-live="polite">
      {inspection ? (
        <CollapsibleSection
          title={isInspecting || isAnalyzing ? "Analyzing your data…" : "Data inspection"}
          subtitle={inspectionSubtitle}
          defaultOpen={!isReady}
          autoCollapseWhen={isReady}
        >
          <InspectionCard
            inspection={inspection}
            analyzing={isInspecting || isAnalyzing}
            embedded
          />
        </CollapsibleSection>
      ) : null}

      {(isReady || findings.length > 0) && !showAlternatives ? (
        <CollapsibleSection
          title={isReady ? "Analysis complete ✓" : "Key findings"}
          subtitle={findings.length ? `${findings.length} insight${findings.length === 1 ? "" : "s"}` : "Patterns"}
          badge={findingsBadge}
          defaultOpen={isReady}
        >
          <InsightsCard findings={findings} complete={isReady} embedded />
        </CollapsibleSection>
      ) : null}

      {showAlternatives && recommendation?.alternatives?.length ? (
        <CollapsibleSection title="Other formats" icon="↔" defaultOpen>
          <AlternativesCard
            alternatives={recommendation.alternatives}
            onSelect={onAlternativeSelect}
            onBack={() => brain.setShowAlternatives(false)}
            disabled={loading}
            embedded
          />
        </CollapsibleSection>
      ) : null}

      {error ? <p className="ooa-viz-agent__error">{brain.error}</p> : null}
    </div>
  );
}

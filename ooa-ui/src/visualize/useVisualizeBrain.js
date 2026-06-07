import { useCallback, useEffect, useRef, useState } from "react";
import { runVisualizeBrain } from "./api";

const PHASE = {
  idle: "idle",
  inspecting: "inspecting",
  analyzing: "analyzing",
  ready: "ready",
  error: "error",
};

export function useVisualizeBrain(droppedItems, serverBrain = null) {
  const [phase, setPhase] = useState(PHASE.idle);
  const [inspection, setInspection] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [error, setError] = useState(null);
  const [showAlternatives, setShowAlternatives] = useState(false);
  const itemsKeyRef = useRef("");

  const reset = useCallback(() => {
    setPhase(PHASE.idle);
    setInspection(null);
    setAnalysis(null);
    setRecommendation(null);
    setError(null);
    setShowAlternatives(false);
  }, []);

  const applyBrainResult = useCallback((result) => {
    if (!result?.recommendation) return;
    setInspection(result.inspection ?? null);
    setAnalysis(result.analysis ?? null);
    setRecommendation(result.recommendation);
    setPhase(PHASE.ready);
    setError(null);
    setShowAlternatives(false);
  }, []);

  const runBrain = useCallback(async (items) => {
    setPhase(PHASE.inspecting);
    setError(null);
    setShowAlternatives(false);

    try {
      const result = await runVisualizeBrain(items);
      setPhase(PHASE.analyzing);
      await new Promise((resolve) => {
        window.setTimeout(resolve, 400);
      });
      applyBrainResult(result);
    } catch (err) {
      setError(err.message || "Analysis failed");
      setPhase(PHASE.error);
    }
  }, [applyBrainResult]);

  useEffect(() => {
    const key = JSON.stringify(
      (droppedItems || []).map((item) => item.id || item.queryId),
    );
    if (!droppedItems?.length) {
      itemsKeyRef.current = "";
      reset();
      return;
    }
    if (serverBrain?.recommendation) {
      if (key !== itemsKeyRef.current) {
        itemsKeyRef.current = key;
        applyBrainResult(serverBrain);
      }
      return;
    }
    if (key === itemsKeyRef.current) return;
    itemsKeyRef.current = key;
    runBrain(droppedItems);
  }, [droppedItems, reset, runBrain, serverBrain, applyBrainResult]);

  return {
    phase,
    inspection,
    analysis,
    recommendation,
    findings: analysis?.findings || [],
    error,
    showAlternatives,
    setShowAlternatives,
    isInspecting: phase === PHASE.inspecting,
    isAnalyzing: phase === PHASE.analyzing,
    isReady: phase === PHASE.ready,
    rerun: () => runBrain(droppedItems),
    applyBrainResult,
  };
}

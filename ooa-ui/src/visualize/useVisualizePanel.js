import { useCallback, useEffect, useState } from "react";
import { VISUALIZE_OPEN_EVENT } from "./constants";
import { isDuplicateDrop, parseVisualizeDragPayload } from "./dragPayload";

export default function useVisualizePanel() {
  const [open, setOpen] = useState(false);
  const [droppedItems, setDroppedItems] = useState([]);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [isDraggingFromChat, setIsDraggingFromChat] = useState(false);
  const [lastDropAt, setLastDropAt] = useState(null);

  const openPanel = useCallback(() => setOpen(true), []);
  const closePanel = useCallback(() => setOpen(false), []);
  const togglePanel = useCallback(() => setOpen((value) => !value), []);

  useEffect(() => {
    const onOpenRequest = () => setOpen(true);
    window.addEventListener(VISUALIZE_OPEN_EVENT, onOpenRequest);
    return () => window.removeEventListener(VISUALIZE_OPEN_EVENT, onOpenRequest);
  }, []);

  const notifyDragStart = useCallback(() => {
    setIsDraggingFromChat(true);
  }, []);

  const notifyDragEnd = useCallback(() => {
    setIsDraggingFromChat(false);
    setIsDraggingOver(false);
  }, []);

  const handleDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setIsDraggingOver(true);
  }, []);

  const handleDragLeave = useCallback((event) => {
    const next = event.relatedTarget;
    if (next && event.currentTarget.contains(next)) return;
    setIsDraggingOver(false);
  }, []);

  const handleDrop = useCallback((event) => {
    event.preventDefault();
    setIsDraggingOver(false);
    setIsDraggingFromChat(false);

    const raw = event.dataTransfer.getData("application/x-ooa-visualize")
      || event.dataTransfer.getData("application/json");
    const payload = parseVisualizeDragPayload(raw);
    if (!payload) return;

    setDroppedItems((prev) => {
      if (isDuplicateDrop(prev, payload)) return prev;
      return [...prev, payload];
    });
    setLastDropAt(Date.now());
    setOpen(true);
  }, []);

  const removeItem = useCallback((itemId) => {
    setDroppedItems((prev) => prev.filter((item) => item.id !== itemId));
  }, []);

  const clearItems = useCallback(() => {
    setDroppedItems([]);
  }, []);

  return {
    open,
    droppedItems,
    isDraggingOver,
    isDraggingFromChat,
    lastDropAt,
    openPanel,
    closePanel,
    togglePanel,
    notifyDragStart,
    notifyDragEnd,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    removeItem,
    clearItems,
  };
}

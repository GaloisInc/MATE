import { useState } from "react";

import { UiNode, GraphType } from "../../lib/api";
import { NodeId } from "../../components/Graph";

export interface MouseCoords {
  x: number;
  y: number;
}

const DEFAULT_MOUSE_COORDS: MouseCoords = {
  x: 0,
  y: 0,
};

export const useContextMenu = () => {
  const [contextNodeId, setContextNodeId] = useState<NodeId | undefined>(
    undefined
  );
  const [mouseCoord, setMouseCoord] =
    useState<MouseCoords>(DEFAULT_MOUSE_COORDS);
  const [nodeSelectionChoice, setNodeSelectionChoice] = useState<
    GraphType | undefined
  >(undefined);
  const [shouldShowContextMenu, setShouldShowContextMenu] = useState(false);
  const [contextNode, setContextNode] = useState<UiNode | undefined>(undefined);

  return {
    // state
    contextNode,
    contextNodeId,
    mouseCoord,
    nodeSelectionChoice,
    shouldShowContextMenu,
    // mutators
    setContextNode,
    setContextNodeId,
    setMouseCoord,
    setNodeSelectionChoice,
    setShouldShowContextMenu,
  };
};

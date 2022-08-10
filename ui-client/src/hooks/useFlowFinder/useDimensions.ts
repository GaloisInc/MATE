import { useState } from "react";

import { PanelDimensions } from "../../components/PanelGrid";

const DEFAULT_PANEL_DIMENSIONS: PanelDimensions = {
  graphWindow: { width: 0, height: 0 },
  cardWindow: { width: 0, height: 0 },
  rightSidebar: { width: 0, height: 0 },
};

interface GraphDimensions {
  height: string;
  width: string;
}

const DEFAULT_GRAPH_DIMENSIONS: GraphDimensions = {
  height: "100%",
  width: "100%",
};

export const useDimensions = () => {
  const [panelDimensions, setPanelDimensions] = useState<PanelDimensions>(
    DEFAULT_PANEL_DIMENSIONS
  );
  const [graphDimensions, setGraphDimensions] = useState<GraphDimensions>(
    DEFAULT_GRAPH_DIMENSIONS
  );

  return {
    // state
    graphDimensions,
    panelDimensions,
    // mutators
    setGraphDimensions,
    setPanelDimensions,
  };
};

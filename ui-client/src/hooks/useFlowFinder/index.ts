import { useCallback, useEffect, useRef, useState } from "react";

import { UiNode, GraphType } from "../../lib/api";
import type {
  ContextNodeSelection,
  GraphId,
  NodeId,
} from "../../components/Graph";
import { useContextMenu } from "./useContextMenu";
import { useDimensions } from "./useDimensions";
import {
  useGraphState,
  AnalysisNodesCache,
  FlowFinderNode,
  FlowFinderEdge,
  FlowFinderEdgeData,
  FlowFinderNodeData,
  GraphCache,
  GraphSliceCache,
  NodeCache,
} from "./useGraphState";
import { usePage } from "../usePage";
import {} from "../../lib/api/snapshots";

export { mapApiNodeToFlowFinderNode } from "./graphTools";

export type {
  AnalysisNodesCache,
  FlowFinderEdge,
  FlowFinderNode,
  FlowFinderEdgeData,
  FlowFinderNodeData,
  GraphCache,
  GraphSliceCache,
  NodeCache,
};

interface HookParams {
  buildId: string;
  poiId?: string;
  snapshotId?: string;
}

export const useFlowFinder = ({ buildId, poiId, snapshotId }: HookParams) => {
  const { isLoading, loadingMessage, setIsLoading, setLoadingMessage } =
    usePage();

  const [pauseGraphResize, setPauseGraphResize] = useState(false);
  const graphTargetRef = useRef(null);

  // Selection/Filters/Highlighting/Hiding state
  const [highlightedGraphId, setHighlightedGraphId] = useState<
    GraphId | undefined
  >(undefined);
  const [sinkId, setSinkId] = useState<string | undefined>(undefined);
  const [sourceId, setSourceId] = useState<string | undefined>(undefined);
  const [centerGraphId, setCenterGraphId] = useState<GraphId | undefined>(
    undefined
  );

  // Panel Dimensions state
  const {
    // state
    graphDimensions,
    panelDimensions,
    // mutators
    setGraphDimensions,
    setPanelDimensions,
  } = useDimensions();

  // Context Menu state
  const {
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
  } = useContextMenu();

  // Graphs state
  const {
    // state
    analysisGraphId,
    analysisNodesById,
    annotationsByGraphId,
    background,
    error,
    filters,
    functionNodes,
    binaryName,
    graphCache,
    graphSliceCache,
    hiddenGraphIds,
    hiddenNodeIds,
    insight,
    nodeCache,
    lrgLayoutConfig,
    mergedGraphs,
    stdLayoutConfig,
    // mutators
    onAddAnnotation,
    onUpdateAnnotation,
    onAddNodeCard,
    onAnalyze,
    onSaveSnapshot,
    setAnalysisGraphId,
    setAnalysisNodesById,
    setFilters,
    setGraphCache,
    setGraphSliceCache,
    setHiddenGraphIds,
    setNodeCache,
    setNodeId,
    setSliceCriteria,
  } = useGraphState({
    buildId,
    contextNodeId,
    nodeSelectionChoice,
    poiId,
    setContextNodeId,
    setIsLoading,
    setNodeSelectionChoice,
    snapshotId,
  });

  // handle resizing of panels
  useEffect(() => {
    const newDim = {
      width: `calc(100vw - ${panelDimensions.rightSidebar.width}px)`,
      height: `calc(${panelDimensions.graphWindow.height}px - 24px)`,
    };
    setGraphDimensions((prevDim) => {
      if (prevDim.width === newDim.width && prevDim.height === newDim.height) {
        return prevDim;
      } else {
        return newDim;
      }
    });
  }, [panelDimensions, setGraphDimensions]);

  // handle change in the id of the selected node for the context menu
  useEffect(() => {
    if (contextNodeId === undefined) {
      setContextNode(undefined);
    } else {
      const nodeCacheNodes: UiNode[] = Object.values(nodeCache)
        .map((nc) => nc.nodes)
        .reduce((acc, ns) => acc.concat(ns), []);

      const nodeCacheMatch = nodeCacheNodes.find(
        (n) => n.node_id === contextNodeId
      );

      if (nodeCacheMatch) {
        setContextNode(nodeCacheMatch);
      } else {
        const graphCacheNodes: UiNode[] = Object.values(graphCache)
          .map((gc) => gc.nodes)
          .reduce((acc, ns) => acc.concat(ns), []);

        const graphCacheMatch = graphCacheNodes.find(
          (n) => n.node_id === contextNodeId
        );

        if (graphCacheMatch) {
          setContextNode(graphCacheMatch);
        } else {
          const graphSliceCacheNodes: UiNode[] = Object.values(graphSliceCache)
            .map((gc) => gc.nodes)
            .reduce((acc, ns) => acc.concat(ns), []);

          const graphSliceCacheMatch = graphSliceCacheNodes.find(
            (n) => n.node_id === contextNodeId
          );

          if (graphSliceCacheMatch) {
            setContextNode(graphSliceCacheMatch);
          }
        }
      }
    }
  }, [contextNodeId, graphCache, graphSliceCache, nodeCache, setContextNode]);

  const onSubmitNodeSelection = useCallback(
    (choice: GraphType) => {
      if (contextNodeId !== null) {
        setNodeSelectionChoice(choice);
      } else {
        console.error("No node id for selection");
      }
      setShouldShowContextMenu(false);
    },
    [contextNodeId, setNodeSelectionChoice, setShouldShowContextMenu]
  );

  const onNodeSelection = useCallback(
    (id) => {
      if (analysisGraphId !== undefined) {
        setAnalysisNodesById((prev) => ({
          ...prev,
          [id]: { id, action: "" },
        }));
      }
    },
    [analysisGraphId, setAnalysisNodesById]
  );

  const onContextNodeSelect = useCallback(
    (n: ContextNodeSelection) => {
      setContextNodeId(n.id);
      setMouseCoord(n.mouseCoords);
      setShouldShowContextMenu(true);
    },
    [setContextNodeId, setMouseCoord, setShouldShowContextMenu]
  );

  const onContextNodeDeselect = useCallback(
    (id: NodeId) => {
      setContextNodeId(undefined);
      setShouldShowContextMenu(false);
    },
    [setContextNodeId, setShouldShowContextMenu]
  );

  const onToggleGraph = useCallback(
    (id: GraphId) => {
      setHiddenGraphIds((prevIds) =>
        prevIds.includes(id)
          ? prevIds.filter((i) => i !== id)
          : prevIds.concat(id)
      );
    },
    [setHiddenGraphIds]
  );

  const onDeleteSlice = useCallback(
    (id: GraphId) => {
      setGraphSliceCache((prev) => {
        const { [id]: _, ...remainingGraphs } = prev;
        return remainingGraphs;
      });
    },
    [setGraphSliceCache]
  );

  const onDeleteGraph = useCallback(
    (id: GraphId) => {
      setGraphCache((prev) => {
        const { [id]: _, ...remainingGraphs } = prev;
        return remainingGraphs;
      });
    },
    [setGraphCache]
  );

  const onDeleteNodeGraph = useCallback(
    (id: GraphId) => {
      setNodeCache((prev) => {
        const { [id]: _, ...remainingGraphs } = prev;
        return remainingGraphs;
      });
    },
    [setNodeCache]
  );

  const onToggleAnalysis = useCallback(
    (id: GraphId) => {
      if (id !== analysisGraphId) {
        setAnalysisNodesById({});
        setAnalysisGraphId(id);
      } else {
        setAnalysisGraphId(undefined);
      }
    },
    [analysisGraphId, setAnalysisGraphId, setAnalysisNodesById]
  );

  const onDeleteAnalysisNode = useCallback(
    (id: NodeId) => {
      setAnalysisNodesById((prev) => {
        const { [id]: _, ...remainingAnalysisNodes } = prev;
        return remainingAnalysisNodes;
      });
    },
    [setAnalysisNodesById]
  );

  const onToggleFocusNode = useCallback(
    (id: NodeId) => {
      setAnalysisNodesById((prev) => ({
        ...prev,
        [id]: {
          ...prev[id],
          action: prev[id].action === "focus" ? "" : "focus",
        },
      }));
    },
    [setAnalysisNodesById]
  );

  const onToggleAvoidNode = useCallback(
    (id: NodeId) => {
      setAnalysisNodesById((prev) => ({
        ...prev,
        [id]: {
          ...prev[id],
          action: prev[id].action === "avoid" ? "" : "avoid",
        },
      }));
    },
    [setAnalysisNodesById]
  );

  const onSetSinkId = useCallback(() => {
    setSinkId(contextNodeId);
    setShouldShowContextMenu(false);
  }, [contextNodeId, setShouldShowContextMenu]);

  const onSetSourceId = useCallback(() => {
    setSourceId(contextNodeId);
    setShouldShowContextMenu(false);
  }, [contextNodeId, setShouldShowContextMenu]);

  const pauseGraphResizing = useCallback(() => setPauseGraphResize(true), []);

  const unPauseGraphResizing = useCallback(
    () => setPauseGraphResize(false),
    []
  );

  const onMouseEnter = useCallback(
    (id: string) => id !== analysisGraphId && setHighlightedGraphId(id),
    [analysisGraphId, setHighlightedGraphId]
  );

  const onMouseLeave = useCallback(
    (id: string) => id !== analysisGraphId && setHighlightedGraphId(undefined),
    [analysisGraphId, setHighlightedGraphId]
  );

  const onContextMenuLeave = useCallback(
    () => setShouldShowContextMenu(false),
    [setShouldShowContextMenu]
  );

  const onCenterGraph = useCallback(
    (id: GraphId) =>
      setCenterGraphId((prevCenterGraphId: GraphId | undefined) =>
        prevCenterGraphId === id ? undefined : id
      ),
    [setCenterGraphId]
  );

  return {
    // state
    analysisGraphId,
    analysisNodesById,
    annotationsByGraphId,
    background,
    centerGraphId,
    contextNode,
    error,
    filters,
    functionNodes,
    binaryName,
    graphCache,
    graphDimensions,
    graphSliceCache,
    graphTargetRef,
    hiddenGraphIds,
    hiddenNodeIds,
    highlightedGraphId,
    insight,
    isLoading,
    loadingMessage,
    lrgLayoutConfig,
    mergedGraphs,
    mouseCoord,
    nodeCache,
    pauseGraphResize,
    shouldShowContextMenu,
    sinkId,
    sourceId,
    stdLayoutConfig,

    // event handlers
    onAddAnnotation,
    onUpdateAnnotation,
    onAddNodeCard,
    onAnalyze,
    onCenterGraph,
    onContextMenuLeave,
    onContextNodeDeselect,
    onContextNodeSelect,
    onDeleteAnalysisNode,
    onDeleteGraph,
    onDeleteNodeGraph,
    onDeleteSlice,
    onMouseEnter,
    onMouseLeave,
    onNodeSelection,
    onSaveSnapshot,
    onSetSinkId,
    onSetSourceId,
    onSubmitNodeSelection,
    onToggleAnalysis,
    onToggleAvoidNode,
    onToggleFocusNode,
    onToggleGraph,
    pauseGraphResizing,
    setFilters,
    setHighlightedGraphId,
    setLoadingMessage,
    setNodeId,
    setPanelDimensions,
    setPauseGraphResize,
    setSliceCriteria,
    unPauseGraphResizing,
  };
};

import { useCallback, useEffect, useState } from "react";

import {
  createFlowFinderSnapshot,
  getFlowFinderPOI,
  getFlowFinderSnapshotById,
  getGraph,
  getGraphSlice,
  getNodeById,
} from "../../lib/api";
import type {
  FlowFinderAnnotation,
  FlowFinderAnnotationsByGraphId,
  GraphSliceApiParams,
  POIGraphRequestAPIParams,
  GraphType,
  NewFlowFinderSnapshot,
  UiGraph,
  UiGraphSlice,
  UiNodeGraph,
} from "../../lib/api";
import {
  generateGraphKey,
  generateSliceKey,
  generateNodeKey,
  parseGraphKey,
  parseNodeKey,
  parseSliceKey,
} from "./keyTools";
import { mergeGraphs, processGraphRequests, updateCache } from "./graphTools";
import type {
  FlowFinderEdge,
  FlowFinderEdgeData,
  FlowFinderNode,
  FlowFinderNodeData,
  MergedGraph,
} from "./graphTools";
import { useFunctionNodes } from "../api/useFunctionNodes";
import { useBuild } from "../api/useBuild";
import type { FilterChoice } from "../../components/Filters";
import type {
  GraphId,
  LayoutConfig,
  LayoutName,
  NodeId,
} from "../../components/Graph";
import type { AnalysisNode } from "../../components/GraphCard";
import type { SliceSelectionCriteria } from "../../components/SliceSelector";

export type GraphCache = Record<GraphId, UiGraph>;
export type GraphSliceCache = Record<GraphId, UiGraphSlice>;
export type NodeCache = Record<NodeId, UiNodeGraph>;
export type AnalysisNodesCache = Record<string, AnalysisNode>;

export type {
  FlowFinderEdge,
  FlowFinderEdgeData,
  FlowFinderNode,
  FlowFinderNodeData,
};

export const DEFAULT_GRAPH_LAYOUT: LayoutName = "dagre";
export const LARGE_GRAPH_LAYOUT: LayoutName = "klay";

const LAYOUT_CONFIG: LayoutConfig = {
  name: DEFAULT_GRAPH_LAYOUT,
  animate: true,
  animationDuration: 1500,
  fit: true,
  edgeSep: 10,
  nodeDimensionsIncludeLabels: true,
};

interface HookParams {
  // from useParams
  buildId: string;
  poiId?: string;
  snapshotId?: string;
  // from useContextMenu
  // -- state
  contextNodeId?: string;
  nodeSelectionChoice?: GraphType;
  // -- mutators
  setContextNodeId: (id?: NodeId) => void;
  setNodeSelectionChoice: (c?: GraphType) => void;
  // from usePage
  setIsLoading: (l: boolean) => void;
}

export const useGraphState = ({
  buildId,
  contextNodeId,
  nodeSelectionChoice,
  poiId,
  setContextNodeId,
  setIsLoading,
  setNodeSelectionChoice,
  snapshotId,
}: HookParams) => {
  const [analysisGraphToHide, setAnalysisGraphToHide] =
    useState<GraphId | null>(null);
  const [analysisGraphId, setAnalysisGraphId] = useState<string | undefined>(
    undefined
  );
  const [analysisNodesById, setAnalysisNodesById] =
    useState<AnalysisNodesCache>({});

  const [background, setBackground] = useState<string | undefined>(undefined);

  const [error, setError] = useState<string | null>(null);

  const [filters, setFilters] = useState<FilterChoice[]>(["MemoryLocation"]);

  const [binaryName, setBinaryName] = useState<string | undefined>(undefined);
  const [graphCache, setGraphCache] = useState<GraphCache>({});
  const [graphSliceCache, setGraphSliceCache] = useState<GraphSliceCache>({});
  const [annotationsByGraphId, setAnnotationsByGraphId] =
    useState<FlowFinderAnnotationsByGraphId>({});
  const [hiddenGraphIds, setHiddenGraphIds] = useState<GraphId[]>([]);
  const [hiddenNodeIds, setHiddenNodeIds] = useState<Set<NodeId>>(new Set());

  const [insight, setInsight] = useState<string | undefined>(undefined);

  const [lrgLayoutConfig] = useState<LayoutConfig>({
    ...LAYOUT_CONFIG,
    name: LARGE_GRAPH_LAYOUT,
  });

  const [mergedGraphs, setMergedGraphs] = useState<MergedGraph>([]);
  const [nodeCache, setNodeCache] = useState<NodeCache>({});

  const [nodeId, setNodeId] = useState<string | undefined>(undefined);

  const [sliceCriteria, setSliceCriteria] =
    useState<SliceSelectionCriteria | null>(null);

  const [stdLayoutConfig] = useState<LayoutConfig>({
    ...LAYOUT_CONFIG,
    name: DEFAULT_GRAPH_LAYOUT,
    // HACK: this is in case you need to understand where dagre is positioning things...
    // transform: (node: SingularElementArgument, pos: Position) => {
    //   console.log(node, pos);
    //   return pos;
    // },
  });

  const processGraphRequestResponses = useCallback(
    (responses: any[]) => {
      responses.forEach((value) => {
        switch (value.request_kind) {
          case "slice":
            const { slice } = value;
            const { source, sink, kind, focusnodeIds, avoidNodeIds } = slice;
            const sliceKey = generateSliceKey({
              build_id: buildId,
              source_id: source,
              sink_id: sink,
              kind,
              focus_node_ids: focusnodeIds,
              avoid_node_ids: avoidNodeIds,
            });
            setGraphSliceCache((prevSliceCache) =>
              updateCache({
                prevCache: prevSliceCache,
                newItem: slice,
                newItemKey: sliceKey,
              })
            );
            break;
          case "graph":
            const { graph } = value;
            const graphKey = generateGraphKey({
              build_id: buildId,
              kind: graph.kind,
              origin_node_ids: graph.originNodeIds,
            });
            setGraphCache((prevGraphCache) =>
              updateCache({
                prevCache: prevGraphCache,
                newItem: graph,
                newItemKey: graphKey,
              })
            );
            break;
          case "node":
            const { graphNode } = value;
            const nodeKey = generateNodeKey({
              build_id: buildId,
              node_id: graphNode.nodes[0].node_id,
            });
            setNodeCache((prevNodeCache) =>
              updateCache({
                prevCache: prevNodeCache,
                newItem: graphNode,
                newItemKey: nodeKey,
              })
            );
            break;
          default:
            console.error(`Unknown request_kind(${value.request_kind})`);
        }
      });
    },
    [buildId, setGraphCache, setGraphSliceCache, setNodeCache]
  );

  const wrapper = useCallback(
    <T>(
      fetch: () => Promise<T>,
      store: (d: T) => void,
      cleanup: () => void
    ) => {
      setIsLoading(true);
      setError(null);
      fetch()
        .then(store)
        .catch((e: any) => {
          console.error(e);
          setError(e.message);
        })
        .finally(() => {
          setIsLoading(false);
          cleanup();
        });
    },
    [setIsLoading]
  );

  const fetchGraphSlice = useCallback(
    async (params: GraphSliceApiParams) => {
      const sliceKey = generateSliceKey(params);

      if (!graphSliceCache[sliceKey]) {
        wrapper(
          () => getGraphSlice(params),
          (graphData) => {
            setGraphSliceCache((prevSliceCache) => ({
              ...prevSliceCache,
              [sliceKey]: {
                ...graphData,
                enabled: true,
                highlighted: false,
              },
            }));
          },
          () => {}
        );
      }
    },

    [graphSliceCache, setGraphSliceCache, wrapper]
  );

  const fetchNode = useCallback(
    (nodeId: NodeId | undefined, cleanupFn: () => void) => {
      if (nodeId !== undefined) {
        const nodeKey = generateNodeKey({ build_id: buildId, node_id: nodeId });
        if (!nodeCache[nodeKey]) {
          wrapper(
            () =>
              getNodeById({
                build_id: buildId,
                node_id: nodeId,
              }),
            (nodeGraph) => {
              setNodeCache((prevNodeCache) =>
                updateCache({
                  prevCache: prevNodeCache,
                  newItem: nodeGraph,
                  newItemKey: nodeKey,
                })
              );
            },
            cleanupFn
          );
        }
      }
    },
    [buildId, nodeCache, wrapper]
  );

  const { functionNodes } = useFunctionNodes({ buildId });
  const { builds, buildsFetchErrors } = useBuild({ buildIds: [buildId] });

  // fetch background and insight text if we have loaded a POI
  useEffect(() => {
    if (snapshotId) {
      if (poiId) {
        getFlowFinderPOI(poiId).then(({ insight, background }) => {
          setInsight(insight);
          setBackground(background);
        });
      } else {
        setInsight(undefined);
        setBackground(undefined);
      }

      wrapper(
        () =>
          getFlowFinderSnapshotById(snapshotId).then(
            ({
              user_annotations = {},
              graph_requests = [],
              hidden_node_ids = [],
              hidden_graph_ids = [],
              filters = [],
            }) => {
              setAnnotationsByGraphId(user_annotations);
              setHiddenNodeIds(new Set(hidden_node_ids));
              setHiddenGraphIds(hidden_graph_ids);
              setFilters(filters);
              return processGraphRequests(graph_requests);
            }
          ),
        processGraphRequestResponses,
        () => {}
      );
    } else if (!poiId) {
      setInsight(undefined);
      setBackground(undefined);
    } else {
      wrapper(
        () =>
          getFlowFinderPOI(poiId).then(
            ({ insight, background, graph_requests = [] }) => {
              setInsight(insight);
              setBackground(background);

              return processGraphRequests(graph_requests);
            }
          ),
        processGraphRequestResponses,
        () => {}
      );
    }
  }, [buildId, poiId, processGraphRequestResponses, snapshotId, wrapper]);

  // fetch the build's binary name
  useEffect(() => {
    if (builds[0]) {
      setBinaryName(
        builds[0].bitcodeArtifact.attributes.binary_filename as string
      );
    } else if (buildsFetchErrors[0]) {
      setError(buildsFetchErrors[0].message);
    }
  }, [builds, buildsFetchErrors]);

  // fetch individual node specified by the user
  useEffect(() => {
    fetchNode(nodeId, () => setNodeId(undefined));
  }, [fetchNode, nodeId]);

  // fetch individual graph-slice with criteria specified by user
  useEffect(() => {
    if (sliceCriteria !== null) {
      const { source_id, sink_id, kind } = sliceCriteria;

      fetchGraphSlice({ build_id: buildId, source_id, sink_id, kind });
      setSliceCriteria(null);
    }
  }, [buildId, fetchGraphSlice, sliceCriteria]);

  // fetch individual graph based on user's context menu choice
  useEffect(() => {
    if (nodeSelectionChoice !== undefined && contextNodeId !== undefined) {
      const key = generateGraphKey({
        build_id: buildId,
        kind: nodeSelectionChoice,
        origin_node_ids: [contextNodeId],
      });

      if (!graphCache[key]) {
        wrapper(
          () =>
            getGraph({
              build_id: buildId,
              origin_node_ids: [contextNodeId],
              kind: nodeSelectionChoice,
            }),
          (graph) =>
            setGraphCache((prevGraphCache) => ({
              ...prevGraphCache,
              [key]: {
                ...graph,
                enabled: true,
                highlighted: false,
              },
            })),
          () => {
            setNodeSelectionChoice(undefined);
            setContextNodeId(undefined);
          }
        );
      }
    }
  }, [
    buildId,
    contextNodeId,
    graphCache,
    nodeSelectionChoice,
    setContextNodeId,
    setGraphCache,
    setNodeSelectionChoice,
    wrapper,
  ]);

  // merge nodes/graphs/graph-slices for our Graph component
  useEffect(() => {
    const mergedGraphs = mergeGraphs({
      graphCache,
      graphSliceCache,
      nodeCache,
    });

    setMergedGraphs((prevGraphs) =>
      mergedGraphs.length === prevGraphs.length ? prevGraphs : mergedGraphs
    );

    const filterNodeIds = mergedGraphs
      .flatMap((g) => g.nodes.filter((n) => filters.includes(n.data.node_kind)))
      .map((n) => n.id);
    setHiddenNodeIds(new Set(filterNodeIds));

    if (analysisGraphToHide) {
      setHiddenGraphIds((prevIds) => prevIds.concat(analysisGraphToHide));
      setAnalysisGraphToHide(null);
    }
  }, [
    nodeCache,
    graphCache,
    graphSliceCache,
    analysisGraphToHide,
    setMergedGraphs,
    filters,
  ]);

  // focus on specific graph-slice for focus/avoid node analysis
  useEffect(() => {
    if (analysisGraphId) {
      setAnalysisNodesById((prevAnalysisNodesById) => {
        const { avoidNodeIds, focusNodeIds } = graphSliceCache[analysisGraphId];
        return {
          ...prevAnalysisNodesById,
          ...avoidNodeIds?.reduce(
            (acc, id) => ({ ...acc, [id]: { id, action: "avoid" } }),
            {}
          ),
          ...focusNodeIds?.reduce(
            (acc, id) => ({ ...acc, [id]: { id, action: "focus" } }),
            {}
          ),
        };
      });
    }
  }, [analysisGraphId, graphSliceCache]);

  const onAnalyze = useCallback(
    (id: GraphId) => {
      const { source, sink, kind } = graphSliceCache[id];
      const focus_node_ids = Object.values(analysisNodesById)
        .filter((n) => n.action === "focus")
        .map((n) => n.id);
      const avoid_node_ids = Object.values(analysisNodesById)
        .filter((n) => n.action === "avoid")
        .map((n) => n.id);
      fetchGraphSlice({
        build_id: buildId,
        source_id: source,
        sink_id: sink,
        kind,
        focus_node_ids,
        avoid_node_ids,
      });
      setAnalysisGraphId(undefined);
      setAnalysisNodesById({});
      setAnalysisGraphToHide(id);
    },
    [analysisNodesById, graphSliceCache, buildId, fetchGraphSlice]
  );

  const onAddNodeCard = useCallback(() => {
    fetchNode(contextNodeId, () => {});
  }, [contextNodeId, fetchNode]);

  const onAddAnnotation = useCallback(
    (graphId: GraphId, annotation: string, createdAt: number) => {
      setAnnotationsByGraphId((prev) => ({
        ...prev,
        [graphId]: [
          {
            graphId,
            annotation,
            createdAt,
          },
        ].concat(prev[graphId] ?? []),
      }));
    },
    []
  );

  const onUpdateAnnotation = useCallback((annotation: FlowFinderAnnotation) => {
    const { graphId } = annotation;

    setAnnotationsByGraphId((prev) => {
      const idx = prev[graphId].findIndex(
        (a) => a.createdAt === annotation.createdAt
      );

      if (idx >= 0) {
        prev[graphId][idx] = annotation;
        return prev;
      } else {
        return {
          ...prev,
          [annotation.graphId]: [annotation],
        };
      }
    });
  }, []);

  const onCreateSnapshot = useCallback(
    (label: string, poi_result_id?: string) => {
      const nodeApiRequests = Object.keys(nodeCache)
        .map(parseNodeKey)
        .map<POIGraphRequestAPIParams>((nodeApiRequest) => ({
          ...nodeApiRequest,
          request_kind: "node",
        }));

      const graphApiRequests = Object.keys(graphCache)
        .map(parseGraphKey)
        .map<POIGraphRequestAPIParams>((graphApiRequest) => ({
          ...graphApiRequest,
          request_kind: "graph",
        }));

      const sliceApiRequests = Object.keys(graphSliceCache)
        .map(parseSliceKey)
        .map<POIGraphRequestAPIParams>((sliceApiRequest) => ({
          ...sliceApiRequest,
          request_kind: "slice",
        }));

      const flowFinderSnapshot: NewFlowFinderSnapshot = {
        user_annotations: annotationsByGraphId ?? {},
        label,
        filters: filters,
        graph_requests: nodeApiRequests
          .concat(graphApiRequests)
          .concat(sliceApiRequests),
        hidden_graph_ids: hiddenGraphIds,
        hidden_node_ids: Array.from(hiddenNodeIds),
        ...(poi_result_id ? { poi_result_id } : null),
      };

      createFlowFinderSnapshot(flowFinderSnapshot, buildId);
    },
    [
      annotationsByGraphId,
      buildId,
      filters,
      graphCache,
      graphSliceCache,
      hiddenGraphIds,
      hiddenNodeIds,
      nodeCache,
    ]
  );

  const onSaveSnapshot = useCallback(
    (label: string) => {
      onCreateSnapshot(label, poiId);
    },
    [onCreateSnapshot, poiId]
  );

  return {
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
    setHiddenNodeIds,
    setNodeCache,
    setNodeId,
    setMergedGraphs,
    setSliceCriteria,
  };
};

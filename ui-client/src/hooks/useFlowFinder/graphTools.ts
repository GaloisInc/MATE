import {
  getGraph,
  getGraphSlice,
  getNodeById,
  EMPTY_FUNCTION_ID,
  EMPTY_SOURCE_ID,
} from "../../lib/api";
import type {
  ApiNode,
  GraphApiParams,
  GraphSliceApiParams,
  NodeApiParams,
  POIGraphRequestAPIParams,
  UiEdge,
  UiNode,
} from "../../lib/api";
import type {
  EdgeData,
  NodeData,
  GraphData,
  GraphEdge,
  GraphNode,
} from "../../components/Graph";
import type { GraphCache, GraphSliceCache, NodeCache } from ".";

export type FlowFinderEdgeData = EdgeData & UiEdge;
export type FlowFinderNodeData = NodeData & UiNode;
export type FlowFinderEdge = GraphEdge<FlowFinderEdgeData>;
export type FlowFinderNode = GraphNode<FlowFinderNodeData>;
export type FlowFinderGraph = GraphData<FlowFinderNodeData, FlowFinderEdgeData>;
export type MergedGraph = FlowFinderGraph[];

export const mapApiNodeToFlowFinderNode = (node: ApiNode): FlowFinderNode => {
  return {
    id: node.node_id,
    data: {
      id: node.node_id,
      graphIds: [],
      isParent: node.node_kind === "Function" || node.node_kind === "Source",
      ...(node.source_id !== EMPTY_SOURCE_ID && node.source_id
        ? { parent: node.source_id }
        : node.function_id !== EMPTY_FUNCTION_ID && node.function_id
        ? { parent: node.function_id }
        : null),
      ...node,
    },
  };
};

export const mapUiEdgeToFlowFinderEdge = (edge: UiEdge): FlowFinderEdge => {
  return {
    id: edge.id,
    data: {
      source: edge.source_id,
      target: edge.target_id,
      graphIds: [],
      ...edge,
      id: edge.id,
    },
  };
};

export const processGraphRequests = (
  graph_requests: POIGraphRequestAPIParams[]
) => {
  if (graph_requests.length > 0) {
    const requests =
      graph_requests?.map((g) => {
        const { request_kind } = g;
        switch (request_kind) {
          case "node":
            return getNodeById(g as NodeApiParams).then((r) => ({
              graphNode: r,
              request_kind,
            }));
          case "graph":
            return getGraph(g as GraphApiParams).then((r) => ({
              graph: r,
              request_kind,
            }));
          case "slice":
            return getGraphSlice(g as GraphSliceApiParams).then((r) => ({
              slice: r,
              request_kind,
            }));
          default:
            console.error(`Unknown request_kind (${request_kind})`);
            return new Promise((succeed, fail) =>
              fail(`Unknown request_kind (${request_kind})`)
            );
        }
      }, []) ?? [];
    return Promise.all(requests);
  } else {
    return Promise.all([]);
  }
};

export const mergeGraphs = ({
  graphCache,
  graphSliceCache,
  nodeCache,
}: {
  graphCache: GraphCache;
  graphSliceCache: GraphSliceCache;
  nodeCache: NodeCache;
}) => {
  const nodeGraphs = Object.entries(nodeCache).map(([id, nodeGraph]) => ({
    id,
    nodes: nodeGraph.nodes.map(mapApiNodeToFlowFinderNode),
    edges: [],
  }));
  const graphs = Object.entries(graphCache).map(([id, graph]) => ({
    id,
    nodes: graph.nodes.map(mapApiNodeToFlowFinderNode),
    edges: graph.edges.map(mapUiEdgeToFlowFinderEdge),
  }));
  const graphSlices = Object.entries(graphSliceCache).map(([id, slice]) => ({
    id,
    nodes: slice.nodes.map(mapApiNodeToFlowFinderNode),
    edges: slice.edges.map(mapUiEdgeToFlowFinderEdge),
  }));

  return [...nodeGraphs, ...graphs, ...graphSlices];
};

type ValueOf<T> = T[keyof T];

export const updateCache = <A, K extends keyof A, B extends ValueOf<A>>({
  prevCache,
  newItem,
  newItemKey,
}: {
  prevCache: A;
  newItem: B;
  newItemKey: K;
}): A => {
  return prevCache[newItemKey]
    ? prevCache
    : { ...prevCache, [newItemKey]: newItem };
};

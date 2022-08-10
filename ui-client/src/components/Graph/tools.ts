import {
  Core,
  EdgeSingular,
  ElementDefinition,
  ElementsDefinition,
  NodeCollection,
  NodeSingular,
  SingularElementArgument,
} from "cytoscape";
import { Graph as GraphLib } from "graphlib";

import {
  CollapseData,
  EdgeData,
  GraphData,
  GraphEdge,
  GraphId,
  GraphNode,
  LayoutConfig,
  NodeData,
  NodeId,
} from "./types";

import {
  ADDED_EDGE_CLASS,
  COLLAPSED_CLASS,
  FILTER_CLASS,
  HIDDEN_CLASS,
  HIGHLIGHTED_CLASS,
  UNFILTER_CLASS,
} from "./styles";

type EdgeRecord = EdgeData;
type EdgeMap = Record<string, EdgeRecord>;

const KEY_JOIN_TOKEN = "\u200B"; // Zero-width space (figure we'll never have this as a character...)

export const LARGE_GRAPH_OBJ_COUNT = 1000;

// some utility functions to help us out
const union = <T>(a?: T[], b?: T[]): T[] => {
  if (a && b) {
    return a.concat(b.filter((i: T) => a.includes(i)));
  } else if (a) {
    return a;
  } else if (b) {
    return b;
  } else {
    return [];
  }
};

const intersection = <T>(a?: T[], b?: T[]): T[] => {
  if (a && b) {
    return a.filter((i: T) => b.includes(i))
  } else {
    return [];
  }
};
const haveSameElements = <T>(a: T[], b: T[]) =>
  intersection(a, b).length === a.length;
const uniquify = <T>(a: T[]) => Array.from(new Set(a));

const hasNoEdgesToChildren = (childIds: string[]) => (e: EdgeSingular) => {
  const { source, target } = e.data();
  return !childIds.includes(source) || !childIds.includes(target);
};

const getCollapseData = (cy: Core, nodeId: string) =>
  cy.scratch(`${nodeId}-${COLLAPSED_CLASS}`);
const stashCollapseData = (cy: Core, nodeId: string, data: CollapseData) =>
  cy.scratch(`${nodeId}-${COLLAPSED_CLASS}`, data);
const clearCollapseData = (cy: Core, nodeId: string) =>
  cy.scratch(`${nodeId}-${COLLAPSED_CLASS}`, undefined);

export const genEdgeId = (source: string, target: string, kind?: string) =>
  (kind ? [source, target, kind] : [source, target]).join(KEY_JOIN_TOKEN);

const genMapperFromEdgeToDataForChildrenWithParent =
  (childIds: string[], parentId: string) =>
  (e: EdgeSingular): EdgeData => {
    const { source, target, graphIds, kind }: EdgeData = e.data();
    const classes = e.classes()

    if (childIds.includes(source)) {
      const id = genEdgeId(parentId, target, kind);
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      return { id, source: parentId, target, graphIds, kind, classes };
    } else {
      const id = genEdgeId(source, parentId, kind);
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      return { id, source, target: parentId, graphIds, kind, classes };
    }
  };

const toUniqueEdges = ([edgeMap]: EdgeMap[], edge: EdgeData) => {
  const { source, target, kind, graphIds, classes } = edge;
  const id = genEdgeId(source, target, kind);

  if (edgeMap[id]) {
    edgeMap[id].graphIds = union(edgeMap[id].graphIds, graphIds)
    edgeMap[id].classes = intersection(edgeMap[id].classes, classes);
  } else {
    edgeMap[id] = edge;
  }

  return [edgeMap];
};

const mapEdgeDataToElementDefinition = (e: EdgeData): ElementDefinition => ({
  group: "edges",
  data: { ...e },
  // eslint-disable-next-line @typescript-eslint/ban-ts-comment
  // @ts-ignore
  classes: e.classes,
});

export const extractCollapseData = (
  cy: Core,
  node: NodeSingular
): CollapseData => {
  const parentId = node.id();

  if (node.isParent() && !node.isChildless()) {
    const allChildren = node.children();
    const childParents = allChildren.filter((c) => c.data().isParent);

    if (!childParents.empty()) {
      childParents.forEach((p) => {
        collapseNode(cy, p);
      });
    }

    const children = node.children();
    const childIds = children.map((c) => c.id());
    const edges = children.connectedEdges();

    const edgesToAdd = edges
      .filter(hasNoEdgesToChildren(childIds))
      .map(genMapperFromEdgeToDataForChildrenWithParent(childIds, parentId))
      .reduce<EdgeMap[]>(toUniqueEdges, [{} as EdgeMap])
      .flatMap((m) => Object.values(m))
      .map(mapEdgeDataToElementDefinition);

    return { children, edges, edgesToAdd, parentId };
  } else {
    return (
      getCollapseData(cy, parentId) ?? {
        children: cy.collection(),
        edges: cy.collection(),
        edgesToAdd: [],
        parentId,
      }
    );
  }
};

export const stashChildData = (
  cy: Core,
  parentNode: NodeSingular,
  { children, edges, edgesToAdd, parentId }: CollapseData
) => {
  cy.batch(() => {
    stashCollapseData(cy, parentId, { children, edges, edgesToAdd, parentId });

    cy.add(edgesToAdd).addClass(ADDED_EDGE_CLASS);
    children.forEach((c) => {
      c.move({ parent: null });
      c.data("parent", null);
    });

    children.addClass(COLLAPSED_CLASS);
    parentNode.scratch(COLLAPSED_CLASS, true);
  });
};

export const collapseNode = (cy: Core, coll: NodeCollection) => {
  const parentNode = coll[0];
  if (parentNode.isParent()) {
    const collapseData = extractCollapseData(cy, parentNode);
    stashChildData(cy, parentNode, collapseData);
  }
};

export const expandNode = (cy: Core, coll: NodeCollection) => {
  const parentNode = coll[0];
  const parentId = parentNode.data().id;
  const scratchData = getCollapseData(cy, parentId);
  clearCollapseData(cy, parentId);

  if (scratchData) {
    const { children, edges } = scratchData;

    cy.batch(() => {
      cy.remove(parentNode.connectedEdges(`.${ADDED_EDGE_CLASS}`));

      edges.removeClass(COLLAPSED_CLASS);
      children.removeClass(COLLAPSED_CLASS);
      children.forEach((c: NodeSingular) => {
        c.move({ parent: parentId });
        c.data("parent", parentId);
      });
      parentNode.removeClass(COLLAPSED_CLASS);

      parentNode.scratch(COLLAPSED_CLASS, false);
    });
  }
};

const hideNode = (node: NodeSingular) => {
  node.addClass(HIDDEN_CLASS)
  // Remove the link to the parent while hidden
  node.parent().forEach((p) => {
    node.scratch(HIDDEN_CLASS, p.id())
    node.move({ parent: null })
  })
};

const showNode = (node: NodeSingular) => {
  node.removeClass(HIDDEN_CLASS)
  // Relink to the parent once unhidden
  const parentId = node.scratch(HIDDEN_CLASS)
  if (parentId) {
    node.move({ parent: parentId })
    node.scratch(HIDDEN_CLASS, undefined)
  }
}

export const hideGraphs = (
  cy: Core,
  hiddenGraphIds: GraphId[],
  focusGraphId?: GraphId,
) => {
  whileUncollapsed(cy, () => {
    if (focusGraphId !== undefined) {
      cy.elements().forEach((e) => {
        const graphIds = e.data("graphIds");
        const isChildOfFocusGraph = graphIds.includes(focusGraphId);

        if (!isChildOfFocusGraph) {
          e.addClass(HIDDEN_CLASS);
        } else {
          e.removeClass(HIDDEN_CLASS);
        }
      });
    } else if (hiddenGraphIds.length > 0) {
      cy.elements().forEach((e: SingularElementArgument) => {
        const graphIds = e.data("graphIds");
         if (graphIds) {
          const isOnlyChildOfHiddenGraphs = haveSameElements(
            graphIds,
            hiddenGraphIds
          );

          if (isOnlyChildOfHiddenGraphs) {
            if (e.isNode()) {
              hideNode(e)
            } else {
              e.addClass(HIDDEN_CLASS)
            }
          } else {
            if (e.isNode()) {
              showNode(e)
            } else {
              e.removeClass(HIDDEN_CLASS)
            }
          }
        } else {
          console.error(`element(${e.data().id}) has no graphIds`);
        }
      });
    } else {
      cy.nodes().forEach(showNode)
      cy.edges().removeClass(HIDDEN_CLASS)
    }
  })
};

export const collapseAllNodes = (
  cy: Core,
) => {
  cy.startBatch()
  cy.nodes()
    .filter((n: NodeSingular) => isVisible(n))
    .forEach((n: NodeSingular) => toggleNodeCollapse(cy, n))
  cy.endBatch()
};

export const expandAllNodes = (
  cy: Core,
) => {
  cy.startBatch()
  cy.nodes()
    .filter((n: NodeSingular) => isVisible(n) && n.scratch(COLLAPSED_CLASS))
    .forEach((n: NodeSingular) => toggleNodeCollapse(cy, n))
  cy.endBatch()
};

export const whileUncollapsed = (
  cy: Core,
  callback: (() => void),
) => {
  cy.startBatch()

  const old_nodes = new Set(cy.nodes().map((n) => n.id()))
  const top_collapsed: NodeCollection = cy.nodes().filter((n) => n.scratch(COLLAPSED_CLASS) && !n.hasClass(COLLAPSED_CLASS))
  const inner_collapsed: NodeCollection = cy.nodes().filter((n) => n.scratch(COLLAPSED_CLASS) && n.hasClass(COLLAPSED_CLASS))
  top_collapsed.forEach((n: NodeSingular) => toggleNodeCollapse(cy, n))
  inner_collapsed.forEach((n: NodeSingular) => toggleNodeCollapse(cy, n))

  callback();

  inner_collapsed?.forEach((n: NodeSingular) => {
    const shouldReveal = (
      n.children().filter((child) => isVisible(child) && !old_nodes?.has(child.id()))
    )
    if (shouldReveal.empty()) {
      toggleNodeCollapse(cy, n);
    } else {
      console.groupCollapsed(`Uncollapsing ${n.id()} to reveal:`)
      shouldReveal.forEach((n) => console.log(n.id()))
      console.groupEnd()
      old_nodes?.delete(n.id());
    }
  });
  top_collapsed?.forEach((n: NodeSingular) => {
    const shouldReveal = (
      n.children().filter((child) => isVisible(child) && !old_nodes?.has(child.id()))
    )
    if (shouldReveal.empty()) {
      toggleNodeCollapse(cy, n);
    } else {
      console.groupCollapsed(`Uncollapsing ${n.id()} to reveal:`)
      shouldReveal.forEach((n) => console.log(n.id()))
      console.groupEnd()
    }
  });

  cy.endBatch()
};

const isVisible: (element: SingularElementArgument) => boolean  = (
  element: SingularElementArgument
) => {
  const selfIsVisible = ! (
       element.hasClass(HIDDEN_CLASS)
  || element.hasClass(COLLAPSED_CLASS)
  || element.hasClass(FILTER_CLASS)
  )
  if (element.isEdge()) {
    return (
         selfIsVisible
      && isVisible(element.source())
      && isVisible(element.target())
    );
  } else {
    return selfIsVisible;
  }
};

export const renderGraph = (
  cy: Core,
  smallLayoutConfig: LayoutConfig,
  largeLayoutConfig: LayoutConfig,
  isLargeCallback: (isLarge: boolean) => void,
  layoutComplete: (() => void),
) => {
  const toLayout = cy.elements().filter((n) => isVisible(n))
  const elemCount = toLayout.size()
  const useLarge = toLayout.edges().size() > LARGE_GRAPH_OBJ_COUNT
  const layoutConfig = useLarge ? largeLayoutConfig : smallLayoutConfig
  isLargeCallback(useLarge)
  const label = `layout(${layoutConfig.name}) time (${elemCount} elements) #${Date.now()}`;
  console.groupCollapsed(label);
  console.time(label);
  if (elemCount > 0) {
    // HACK: there is some path in cytoscape where, when you remove all elements
    //       it destroys the renderer, such that when you add a new node back in,
    //       cytoscape crashes. What is odd is that once you add a SECOND node,
    //       the renderer is present (and no longer marked as destroyed).
    //       was not able to pin down why this happens, so for now we skip running
    //       the layout in this case. In some cases, the node is rendered and
    //       centered, but in some other cases (which are indeterminate), it will
    //       render the new node in the top-left corner of the graph...
    if (cy.destroyed()) {
      console.log("skipping layout as current cy renderer is marked as destroyed");
      console.timeEnd(label);
      console.groupEnd();
      layoutComplete();
      return;
    }
  } else {
    console.log("layout not re-run as elements are empty");
    console.timeEnd(label);
    console.groupEnd();
    layoutComplete();
    return;
  }
  cy.one("layoutstop", () => {
    console.timeEnd(label);
    console.groupEnd();
    layoutComplete();
  });
  toLayout.layout(layoutConfig).run();
};

export const toggleNodeCollapse = (cy: Core, node: NodeSingular) => {
  node.scratch(COLLAPSED_CLASS) ? expandNode(cy, node) : collapseNode(cy, node);
};

export const highlightGraph = (cy: Core, highlightedGraphId?: GraphId) => {
  cy.elements().removeClass(HIGHLIGHTED_CLASS); // clear previous highlights

  if (highlightedGraphId) {
    cy.elements()
      .filter(":visible")
      .filter((e) => {
        const graphIds = e.data("graphIds");
        if (!graphIds) {
          console.error(`element(${e.data().id}) has no graphIds`);
        }
        return graphIds && graphIds.includes(highlightedGraphId);
      })
      .addClass(HIGHLIGHTED_CLASS);
  }
};

export const mapGraphToElements = (graph: GraphLib): ElementsDefinition => {
  // graphlib returns only node/edge ids when calling nodes/edges respectively
  // so we have to map that into individual calls to get the full node/edge data
  return {
    nodes: graph.nodes().map((id) => graph.node(id)),
    edges: graph.edges().map(({ v, w, name }) => graph.edge(v, w, name)),
  };
};

// NOTE: this is an internal function to be used by findUnhiddenTargets and
//       findUnhiddenSources as there can be cycles and we need to track
//       visited edges between recursive calls
const findUnhiddenByKind = (
  graph: GraphLib,
  hiddenNodeIds: Set<NodeId>,
  target: NodeId,
  kind: "source" | "target",
  visitedCache: Set<string>
): GraphNode<NodeData>[] => {
  return (graph.outEdges(target) || []).reduce((acc, edge) => {
    const edgeId = kind === "target" ? edge.w : edge.v;
    if (visitedCache.has(edgeId)) {
      return acc;
    } else {
      visitedCache.add(edgeId);
      if (hiddenNodeIds.has(edgeId)) {
        return acc;
	// TODO(sm): this disables multi-hop edge linking through hidden nodes,
	// since our current graphs don't need this.
	// If re-enabled, it should be modified to account for edge types along
	// the hidden path.
        //return acc.concat(
        //  findUnhiddenByKind(graph, hiddenNodeIds, edgeId, kind, visitedCache)
        //);
      } else {
        return acc.concat(graph.node(edgeId));
      }
    }
  }, [] as GraphNode<NodeData>[]);
};

const findUnhiddenTargets = (
  graph: GraphLib,
  hiddenNodeIds: Set<NodeId>,
  target: NodeId
): GraphNode<NodeData>[] => {
  const visitedCache = new Set<string>();

  return findUnhiddenByKind(
    graph,
    hiddenNodeIds,
    target,
    "target",
    visitedCache
  );
};

const findUnhiddenSources = (
  graph: GraphLib,
  hiddenNodeIds: Set<NodeId>,
  source: NodeId
): GraphNode<NodeData>[] => {
  const visitedCache = new Set<string>();

  return findUnhiddenByKind(
    graph,
    hiddenNodeIds,
    source,
    "source",
    visitedCache
  );
};

const addEdge = (
  graph: GraphLib,
  source: NodeId,
  target: NodeId,
  data: EdgeData,
  graphIds: GraphId[]
) => {
  const id = genEdgeId(source, target, data.kind);
  graph.setEdge(source, target, {
    id,
    data: {
      ...data,
      id,
      source,
      target,
      graphIds,
    },
  }, id);
};

const getGraphNode = (graph: GraphLib, id: NodeId): GraphNode<NodeData> =>
  graph.node(id);

const getGraphEdge = (
  graph: GraphLib,
  from: NodeId,
  to: NodeId,
  name?: string,
): GraphEdge<EdgeData> => graph.edge(from, to, name);

const remapHiddenEdges = (
  graph: GraphLib,
  hiddenNodeIds: Set<NodeId>
): GraphLib => {
  hiddenNodeIds.forEach((id) => {
    const node = getGraphNode(graph, id);

    if (!node) return;

    const inEdges = graph.inEdges(id) || [];
    const outEdges = graph.outEdges(id) || [];

    uniquify(inEdges.concat(outEdges)).forEach(({ v, w, name }) => {
      const isFromHiddenNode = hiddenNodeIds.has(v);
      const isToHiddenNode = hiddenNodeIds.has(w);
      const edge = getGraphEdge(graph, v, w, name);

      if (isToHiddenNode && !isFromHiddenNode) {
        const nodes = findUnhiddenTargets(graph, hiddenNodeIds, w);
        const sourceNode = getGraphNode(graph, v);

        nodes.forEach((n) => {
          addEdge(
            graph,
            v,
            n.id,
            edge.data,
            intersection(sourceNode.data.graphIds ?? [], n.data.graphIds ?? [])
          );
        });
      } else if (!isToHiddenNode && isFromHiddenNode) {
        const nodes = findUnhiddenSources(graph, hiddenNodeIds, v);
        const targetNode = getGraphNode(graph, w);

        nodes.forEach((n) => {
          addEdge(
            graph,
            n.id,
            w,
            edge.data,
            intersection(targetNode.data.graphIds ?? [], n.data.graphIds ?? [])
          );
        });
      }

      const edgeData = graph.edge(v, w, name);
      graph.setEdge(v, w, { ...edgeData, classes: [FILTER_CLASS] }, name);
    });
  });

  return graph;
};

export const buildGraph = <N extends NodeData, E extends EdgeData>(
  graphs: GraphData<N, E>[],
  hiddenNodeIds: Set<NodeId>
): GraphLib => {
  const graph = graphs.reduce<GraphLib>((graphLib, graph) => {
    graph.nodes.forEach((n) => {
      const { id, data } = n;
      const classes = [
        hiddenNodeIds.has(id) ? FILTER_CLASS : UNFILTER_CLASS,
      ];
      const node = graphLib.node(id);
      const newData = node
        ? {
            ...node.data,
            graphIds: (node.data.graphIds ?? []).concat(graph.id),
          }
        : { ...data, graphIds: [graph.id] };

      graphLib.setNode(id, {
        id,
        classes,
        data: newData,
      });

      if (data.parent) {
        graphLib.setParent(id, data.parent);
      }
    });

    graph.edges.forEach((e) => {
      const {
        id,
        data: { source, target },
      } = e;

      const isHiddenEdge =
        hiddenNodeIds.has(target) || hiddenNodeIds.has(source);
      const classes = [isHiddenEdge ? FILTER_CLASS : UNFILTER_CLASS];
      const edge = graphLib.edge(source, target, id);

      const newData = edge
        ? {
            ...edge.data,
            graphIds: (edge.data.graphIds ?? []).concat(graph.id),
          }
        : {
            ...e.data,
            graphIds: [graph.id],
          };

      graphLib.setEdge(source, target, {
        id,
        classes,
        data: newData,
      }, id);
    });

    return graphLib;
  }, new GraphLib({ compound: true, directed: true, multigraph: true }));

  return remapHiddenEdges(graph, hiddenNodeIds);
};

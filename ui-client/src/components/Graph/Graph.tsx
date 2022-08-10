import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
  CSSProperties,
  ForwardedRef,
} from "react";
import cytoscape from "cytoscape";
import type {
  Core,
  ElementDefinition,
  EventObject,
  Ext,
  Stylesheet,
} from "cytoscape";
import { Graph as GraphLib } from "graphlib";
import CytoscapeComponent from "react-cytoscapejs";
import dagre from "cytoscape-dagre";
import fcose from "cytoscape-fcose";
import cola from "cytoscape-cola";
import klay from "cytoscape-klay";
import euler from "cytoscape-euler";
import { FaCompressArrowsAlt } from "react-icons/fa";
import { CgLayoutGrid, CgLayoutGridSmall, CgLayoutPin } from "react-icons/cg";
import { IoIosWarning } from "react-icons/io";
import { OverlayTrigger, Tooltip } from "react-bootstrap";

import { ProcessingIndicator } from "./ProcessingIndicator";

import type {
  ContextNodeSelection,
  EdgeData,
  GraphData,
  GraphId,
  KeyData,
  LayoutConfig,
  LayoutName,
  NodeData,
  NodeId,
} from "./types";
import {
  buildGraph,
  highlightGraph,
  mapGraphToElements,
  hideGraphs,
  toggleNodeCollapse,
  renderGraph,
  collapseAllNodes,
  expandAllNodes,
} from "./tools";

import { baseStyles } from "./styles";

import "../../styles/Graph.scss";

// NOTE: this is some special jiggery to allow us to forward refs through
//       our Graph component
//       see: https://stackoverflow.com/questions/58469229/react-with-typescript-generics-while-using-react-forwardref/58473012
declare module "react" {
  function forwardRef<T, P = {}>(
    render: (props: P, ref: ForwardedRef<T>) => ReactElement | null
  ): (props: P & RefAttributes<T>) => ReactElement | null;
}

const SUPPORTED_LAYOUTS: Record<LayoutName, Ext> = {
  dagre: dagre,
  fcose: fcose,
  cola: cola,
  klay: klay,
  euler: euler,
};

const DEFAULT_DIM = { width: "100%", height: "100%" };

const PAN_INCREMENT = 10;

interface GraphProps<N extends NodeData, E extends EdgeData> {
  graphs: GraphData<N, E>[];
  hiddenGraphIds: GraphId[];
  hiddenNodeIds: Set<NodeId>;
  layoutConfig: LayoutConfig;
  centerGraphId?: GraphId;
  focusGraphId?: GraphId;
  forceResize?: boolean;
  highlightedGraphId?: GraphId;
  keyData?: KeyData;
  largeGraphFallbackLayoutConfig: LayoutConfig;
  onContextNodeDeselect?: (id: NodeId) => void;
  onContextNodeSelect?: (node: ContextNodeSelection) => void;
  onNodeSelection?: (id: NodeId) => void;
  pauseLayout?: boolean;
  pauseResize?: boolean;
  style?: CSSProperties;
  stylesheets?: Stylesheet[];
}

const GraphRenderer = <
  N extends NodeData,
  E extends EdgeData,
  T extends HTMLDivElement | null
>(
  props: GraphProps<N, E>,
  ref: ForwardedRef<T>
) => {
  const {
    centerGraphId,
    focusGraphId,
    forceResize = false,
    graphs,
    hiddenGraphIds,
    hiddenNodeIds,
    highlightedGraphId,
    keyData,
    largeGraphFallbackLayoutConfig,
    layoutConfig,
    onContextNodeDeselect,
    onContextNodeSelect,
    onNodeSelection,
    pauseLayout = false,
    pauseResize = false,
    style,
    stylesheets = [],
  } = props;

  const graphCount = useRef(graphs.length);
  const graphSize = useRef(0);
  const [cy, setCy] = useState<Core | null>(null);
  const [elements, setElements] = useState<ElementDefinition[] | null>(null);
  const [graph, setGraph] = useState<GraphLib | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [styleDimensions, setStyleDimensions] = useState<{
    width: string | number;
    height: string | number;
  }>({
    width: style?.width ?? DEFAULT_DIM.width,
    height: style?.height ?? DEFAULT_DIM.height,
  });
  const [shouldResize, setShouldResize] = useState(false);
  const [shouldLayout, setShouldLayout] = useState(false);
  const [useLargeGraphLayout, setUseLargeGraphLayout] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

  // HACK: since useState is only run on the first invocation of this component
  //       we use it to have cytoscape load the layouts we need
  //       (NOTE: this does mean clients cannot change layouts dynamically)
  useState(() => {
    cytoscape.use(SUPPORTED_LAYOUTS[layoutConfig.name]);

    if (largeGraphFallbackLayoutConfig) {
      cytoscape.use(SUPPORTED_LAYOUTS[largeGraphFallbackLayoutConfig.name]);
    }
  });

  const captureNodeSelection = useCallback(
    ({ target: [node] }: EventObject) => {
      if (onNodeSelection) {
        const id = node.data().id;
        onNodeSelection(id);
      }
    },
    [onNodeSelection]
  );

  const centerGraph = useCallback(() => {
    cy?.resize();
    cy?.fit();
  }, [cy]);

  const layoutGraph = useCallback(
    () => {
      if (cy) {
        if (!isProcessing) {
          setIsProcessing(true);
          hideGraphs(cy, hiddenGraphIds, focusGraphId);
          renderGraph(
            cy,
            layoutConfig,
            largeGraphFallbackLayoutConfig,
            setUseLargeGraphLayout,
            () => setIsProcessing(false)
          );
        } else {
          setShouldLayout(true);
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [cy, isProcessing, hiddenGraphIds, focusGraphId]
  );

  const showContextMenu = useCallback(
    ({ originalEvent: { x, y }, target: [node] }: EventObject) => {
      if (onContextNodeSelect) {
        const id = node.data().id;
        onContextNodeSelect({
          id,
          mouseCoords: { x, y },
        });

        cy?.one("mouseout", `#${id}`, (e: EventObject) => {
          if (onContextNodeDeselect) {
            onContextNodeDeselect(id);
          }
        });
      }
    },
    [cy, onContextNodeSelect, onContextNodeDeselect]
  );

  const collapseAll = useCallback(() => {
    if (cy) {
      setIsProcessing(true);
      collapseAllNodes(cy);
      hideGraphs(cy, hiddenGraphIds, focusGraphId);
      renderGraph(
        cy,
        layoutConfig,
        largeGraphFallbackLayoutConfig,
        setUseLargeGraphLayout,
        () => setIsProcessing(false)
      );
    }
  }, [
    cy,
    hiddenGraphIds,
    focusGraphId,
    layoutConfig,
    largeGraphFallbackLayoutConfig,
  ]);

  const expandAll = useCallback(() => {
    if (cy) {
      setIsProcessing(true);
      expandAllNodes(cy);
      hideGraphs(cy, hiddenGraphIds, focusGraphId);
      renderGraph(
        cy,
        layoutConfig,
        largeGraphFallbackLayoutConfig,
        setUseLargeGraphLayout,
        () => setIsProcessing(false)
      );
    }
  }, [
    cy,
    hiddenGraphIds,
    focusGraphId,
    layoutConfig,
    largeGraphFallbackLayoutConfig,
  ]);

  const toggleNode = useCallback(
    ({ target: [node] }: EventObject) => {
      if (cy) {
        setIsProcessing(true);
        toggleNodeCollapse(cy, node);
        hideGraphs(cy, hiddenGraphIds, focusGraphId);
        renderGraph(
          cy,
          layoutConfig,
          largeGraphFallbackLayoutConfig,
          setUseLargeGraphLayout,
          () => setIsProcessing(false)
        );
      }
    },
    [
      cy,
      hiddenGraphIds,
      focusGraphId,
      layoutConfig,
      largeGraphFallbackLayoutConfig,
    ]
  );

  // center on given graph
  useEffect(() => {
    if (cy && centerGraphId) {
      const eles = cy
        .elements("node")
        .filter((e) => e.data("graphIds").includes(centerGraphId));
      if (eles.length > 0) {
        cy.fit(eles);
      }
    }
  }, [cy, centerGraphId]);

  // build our graph
  useEffect(() => {
    const graph = buildGraph(graphs, hiddenNodeIds);
    setGraph(graph);

    graphCount.current = graphs.length;
    graphSize.current = graph.nodeCount() + graph.edgeCount();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphs.length, hiddenNodeIds]);

  // update elements in the graph
  useEffect(() => {
    if (graph !== null) {
      const elements = mapGraphToElements(graph);
      if (graphSize.current >= 0) {
        const cytoscapeElems = CytoscapeComponent.normalizeElements(elements);
        setElements(cytoscapeElems);
      }
      setShouldLayout(true);
    }
  }, [graph, largeGraphFallbackLayoutConfig]);

  // trigger layout
  useEffect(() => {
    if (shouldLayout && !pauseLayout) {
      setShouldLayout(false);
      layoutGraph();
    }
  }, [layoutGraph, shouldLayout, pauseLayout]);

  // set up toggling of expand / collapse
  useEffect(() => {
    cy?.removeListener("tap");
    cy?.on("tap", "node[?isParent]", toggleNode);
  }, [cy, toggleNode]);

  // set up context / node selection handlers
  useEffect(() => {
    if (onContextNodeSelect) {
      cy?.on("cxttap", "node", showContextMenu);
    }
    if (onNodeSelection) {
      cy?.on("tap", "node", captureNodeSelection);
    }
  }, [
    cy,
    captureNodeSelection,
    showContextMenu,
    onContextNodeSelect,
    onNodeSelection,
  ]);

  // set up panning via keyboard
  useEffect(() => {
    const arrowHandler = (e: any) => {
      if (isFocused) {
        switch (e.key) {
          case "ArrowUp":
            cy?.panBy({ x: 0, y: -PAN_INCREMENT });
            break;
          case "ArrowDown":
            cy?.panBy({ x: 0, y: PAN_INCREMENT });
            break;
          case "ArrowLeft":
            cy?.panBy({ x: -PAN_INCREMENT, y: 0 });
            break;
          case "ArrowRight":
            cy?.panBy({ x: PAN_INCREMENT, y: 0 });
            break;
        }
      }
    };
    window.document.addEventListener("keydown", arrowHandler);

    return () => {
      window.document.removeEventListener("keydown", arrowHandler);
      return;
    };
  }, [cy, isFocused]);

  // highlight a given graph
  useEffect(() => {
    if (cy) {
      highlightGraph(cy, highlightedGraphId);
    }
  }, [cy, highlightedGraphId]);

  // hide graphs
  useEffect(() => {
    if (cy) {
      setIsProcessing(true);
      hideGraphs(cy, hiddenGraphIds, focusGraphId);
      renderGraph(
        cy,
        layoutConfig,
        largeGraphFallbackLayoutConfig,
        setUseLargeGraphLayout,
        () => setIsProcessing(false)
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cy, focusGraphId, hiddenGraphIds]);

  // determine if we should resize the canvas
  useEffect(() => {
    const { width = DEFAULT_DIM.width, height = DEFAULT_DIM.height } =
      style ?? DEFAULT_DIM;

    if (styleDimensions.width !== width || styleDimensions.height !== height) {
      setStyleDimensions({ width, height });
      setShouldResize(true);
    } else {
      setShouldResize(false);
    }
  }, [style, styleDimensions]);

  // resize the canvas
  useEffect(() => {
    if ((forceResize || shouldResize) && !(pauseResize || highlightedGraphId)) {
      cy?.resize();
    }
  }, [cy, forceResize, highlightedGraphId, pauseResize, shouldResize]);

  return (
    <div
      className="Graph"
      data-testid="graph-wrapper"
      onMouseDown={() => setIsFocused(true)}
      onMouseLeave={() => setIsFocused(false)}
      {...(ref === undefined ? {} : { ref })}
    >
      <FaCompressArrowsAlt className="centerToggle m-2" onClick={centerGraph} />
      <CgLayoutPin className="layoutToggle m-2" onClick={layoutGraph} />
      <CgLayoutGrid className="collapseAll m-2" onClick={collapseAll} />
      <CgLayoutGridSmall className="expandAll m-2" onClick={expandAll} />
      {useLargeGraphLayout && (
        <OverlayTrigger
          key="layoutWarningTooltip"
          placement="bottom"
          overlay={
            <Tooltip id="tooltip-layout-warning">Graph is large</Tooltip>
          }
        >
          <IoIosWarning className="largeLayoutWarning m-2" />
        </OverlayTrigger>
      )}
      <ProcessingIndicator isProcessing={isProcessing} />
      {keyData && (
        <div className="graphKey" style={{ width: style?.width }}>
          <ul>
            {Object.entries(keyData).map(([key, color]) => (
              <li key={key} style={{ color }}>
                {key}
              </li>
            ))}
          </ul>
        </div>
      )}
      {/* the process.env hack is so tests pass as cytoscape is incompatible with Jest for testing :( */}
      {process?.env?.NODE_ENV !== "test" && elements && elements.length > 0 && (
        <CytoscapeComponent
          cy={setCy}
          elements={elements ?? []}
          style={style}
          stylesheet={stylesheets.concat(baseStyles)}
          hideEdgesOnViewport={true}
        />
      )}
    </div>
  );
};

export const Graph = React.forwardRef(GraphRenderer);

import type {
  ClassNames,
  EdgeCollection,
  ElementDefinition,
  NodeCollection,
  NodeSingular,
  Position,
  SingularElementArgument,
} from "cytoscape";

export type GraphId = string;
export type NodeId = string;
export type EdgeId = string;

export interface HiddenObject {
  hidden?: boolean;
}

export interface ChildObject {
  graphIds?: GraphId[];
}

export interface NodeData extends HiddenObject, ChildObject {
  id: NodeId;
  isParent: boolean;
  parent?: string;
  collapsed?: boolean;
}

export interface GraphNode<N extends NodeData> extends ElementDefinition {
  id: NodeId;
  data: N;
}

export interface EdgeData extends HiddenObject, ChildObject {
  id: EdgeId;
  source: NodeId;
  target: NodeId;
  kind?: string;
  classes?: string[];
}

export interface GraphEdge<E extends EdgeData> extends ElementDefinition {
  id: EdgeId;
  data: E;
  isCollapseEdge?: boolean;
}

export interface GraphData<N extends NodeData, E extends EdgeData> {
  id: GraphId;
  nodes: GraphNode<N>[];
  edges: GraphEdge<E>[];
}

export interface CollapseData {
  children: NodeCollection;
  edges: EdgeCollection;
  edgesToAdd: ElementDefinition[];
  parentId: NodeId;
}

export interface RemapData {
  node: NodeSingular;
  incoming: EdgeCollection;
  outgoing: EdgeCollection;
  addedEdges: EdgeCollection;
}

export interface ContextNodeSelection {
  id: NodeId;
  mouseCoords: { x: number; y: number };
}

export type LayoutName = "dagre" | "fcose" | "cola" | "klay" | "euler";

export type LayoutConfig = {
  name: LayoutName;
  [key: string]:
    | string
    | boolean
    | number
    | ((e: SingularElementArgument, p: Position) => void);
};

export type KeyData = Record<string, string>; // label/color

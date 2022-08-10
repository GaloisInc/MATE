import { axiosInstance as axiosClient } from "./axios-instance";
import { processResponse } from "./utils";
import { genEdgeId } from "../../components/Graph/tools";

export type GraphType =
  | "forward_dataflow"
  | "reverse_dataflow"
  | "forward_control_flow"
  | "reverse_control_flow"
  | "forward_control_dependence"
  | "reverse_control_dependence"
  | "callsites"
  | "callers"
  | "callees"
  | "operands"
  | "uses"
  | "forward_points_to"
  | "reverse_points_to"
  | "forward_points_to_reachable"
  | "reverse_points_to_reachable"
  | "forward_allocation"
  | "reverse_allocation"
  | "forward_memory_subregion"
  | "reverse_memory_subregion"
  | "aliased_memory_locations"
  | "signatures";

export type NodeType = "source" | "sink";

// NOTE: This is brittle as we have hard-coded these values here
//       Ideally we'd derive these from the database and either
//       have an API endpoint to fetch them or embed a configuration
//       file that contains them as a part of the UI
//       See https://gitlab-ext.galois.com/mate/MATE/-/issues/1467#note_100951
//       for background on the rationale for choosing this route for the
//       initial implementation
export type NodeKind =
  | "Alloca"
  | "Argument"
  | "ArrayType"
  | "ASMBlock"
  | "ASMGlobalVariable"
  | "ASMInst"
  | "BasicType"
  | "Block"
  | "Call"
  | "CallReturn"
  | "ClassType"
  | "CompositeCachedType"
  | "CompositeType"
  | "Constant"
  | "ConstantFp"
  | "ConstantInt"
  | "ConstantString"
  | "ConstantUndef"
  | "DataflowSignature"
  | "DerivedType"
  | "DWARFArgument"
  | "DWARFLocalVariable"
  | "DWARFType"
  | "EnumType"
  | "Function"
  | "GlobalVariable"
  | "InputSignature"
  | "Instruction"
  | "Invoke"
  | "LLVMType"
  | "Load"
  | "LocalVariable"
  | "MachineBasicBlock"
  | "MachineFunction"
  | "MachineInstr"
  | "Memcpy"
  | "MemoryLocation"
  | "Memset"
  | "Module"
  | "OutputSignature"
  | "ParamBinding"
  | "PLTStub"
  | "Resume"
  | "Ret"
  | "Source"
  | "Store"
  | "StructureType"
  | "SubroutineType"
  | "TranslationUnit"
  | "UnclassifiedNode"
  | "UnionType"
  | "VTable";

export interface ApiNode {
  node_id: string;
  node_kind: NodeKind;
  opcode: string;
  function_id: string;
  label: string;
  source_id: string;
  enabled?: boolean;
  highlighted?: boolean;
}

export interface UiNode extends ApiNode {}

export interface ApiEdge {
  edge_id: string;
  edge_kind: string;
  source_id: string;
  target_id: string;
  highlighted?: boolean;
}

export interface UiEdge extends ApiEdge {
  id: string;
  kind: string;
}

interface GraphApiResponse {
  nodes: ApiNode[];
  edges: ApiEdge[];
}

interface UiBaseGraph {
  nodes: UiNode[];
  edges: UiEdge[];
}

export interface UiNodeGraph extends UiBaseGraph {}

export interface UiGraph extends UiBaseGraph {
  originNodeIds: string[];
  kind: GraphType;
}

export interface UiGraphSlice extends UiBaseGraph {
  kind: GraphType;
  source: string;
  sink: string;
  focusNodeIds?: string[];
  avoidNodeIds?: string[];
}

export type GraphRequestKind = "slice" | "graph" | "node";
export type POIGraphRequestAPIParams = (
  | GraphSliceApiParams
  | GraphApiParams
  | NodeApiParams
) & { request_kind: GraphRequestKind };

const toUiEdge = (e: ApiEdge): UiEdge => ({
  ...e,
  id: genEdgeId(e.source_id, e.target_id, e.edge_kind),
  kind: e.edge_kind,
});

const toUiNode = (n: ApiNode): UiNode => n;

export const displayGraphType = (type: GraphType): string => {
  switch (type) {
    case "forward_dataflow":
      return "Dataflow";
    case "reverse_dataflow":
      return "Reverse dataflow";
    case "forward_control_flow":
      return "Control flow";
    case "reverse_control_flow":
      return "Reverse control flow";
    case "forward_control_dependence":
      return "Forward control dependence";
    case "reverse_control_dependence":
      return "Reverse control dependence";
    case "callsites":
      return "Callsites";
    case "callers":
      return "Callers";
    case "callees":
      return "Callees";
    case "operands":
      return "Operands";
    case "uses":
      return "Uses";
    case "forward_points_to":
      return "Points-to";
    case "reverse_points_to":
      return "Pointed-to";
    case "forward_points_to_reachable":
      return "Points-to reachable";
    case "reverse_points_to_reachable":
      return "Pointed-to reachable";
    case "forward_allocation":
      return "Allocates";
    case "reverse_allocation":
      return "Allocated by";
    case "forward_memory_subregion":
      return "Memory subregions";
    case "reverse_memory_subregion":
      return "Containing memory regions";
    case "aliased_memory_locations":
      return "Aliased memory locations";
    case "signatures":
      return "Signatures";
  }
};

export const EMPTY_FUNCTION_ID = "None";
export const EMPTY_SOURCE_ID = "None";

export interface NodeApiParams {
  build_id: string;
  node_id: string;
}

export const getNodeById = async ({
  build_id,
  node_id,
}: NodeApiParams): Promise<UiNodeGraph> => {
  return axiosClient
    .get(`/api/v1/graphs/${build_id}/nodes/${node_id}`)
    .then(processResponse)
    .then((g: GraphApiResponse) => ({
      edges: g.edges.map(toUiEdge),
      nodes: g.nodes.map(toUiNode),
    }));
};

export interface GraphApiParams {
  build_id: string;
  origin_node_ids: string[];
  kind: GraphType;
}

export const getGraph = async ({
  build_id,
  origin_node_ids,
  kind,
}: GraphApiParams): Promise<UiGraph> => {
  return axiosClient
    .post(`/api/v1/graphs/${build_id}`, {
      build_id,
      origin_node_ids,
      kind,
    })
    .then(processResponse)
    .then((g: GraphApiResponse) => ({
      edges: g.edges.map(toUiEdge),
      kind: kind,
      nodes: g.nodes.map(toUiNode),
      originNodeIds: origin_node_ids,
    }));
};

export interface GraphSliceApiParams {
  build_id: string;
  sink_id: string;
  source_id: string;
  kind: GraphType;
  focus_node_ids?: string[];
  avoid_node_ids?: string[];
}

export const getGraphSlice = async ({
  avoid_node_ids = [],
  build_id,
  focus_node_ids = [],
  kind,
  source_id,
  sink_id,
}: GraphSliceApiParams): Promise<UiGraphSlice> => {
  return axiosClient
    .post(`/api/v1/graphs/${build_id}/slices`, {
      build_id,
      avoid_node_ids,
      focus_node_ids,
      kind,
      source_id,
      sink_id,
    })
    .then(processResponse)
    .then((g: GraphApiResponse) => ({
      avoidNodeIds: avoid_node_ids ?? [], // though the typedef says otherwise, the API can return null for this value which leads to invalid api requests, so default it to the empty list in that case
      edges: g.edges.map(toUiEdge),
      focusNodeIds: focus_node_ids ?? [], // though the typedef says otherwise, the API can return null for this value which leads to invalid api requests, so default it to the empty list in that case
      kind,
      nodes: g.nodes.map(toUiNode),
      sink: sink_id,
      source: source_id,
    }));
};

export const getFunctionNodes = async (buildId: string): Promise<ApiNode[]> => {
  return axiosClient
    .get(`/api/v1/graphs/${buildId}/function-nodes`)
    .then(processResponse);
};

export const getMachineFunctionNodes = async (
  buildId: string
): Promise<ApiNode[]> => {
  return axiosClient
    .get(`/api/v1/graphs/${buildId}/machine-function-nodes`)
    .then(processResponse);
};

import cytoscape from "cytoscape";
import cystoscape, { Stylesheet } from "cytoscape";

import { KeyData } from "../components/Graph/types";
import { NodeKind } from "../lib/api";

export const DetailColors: KeyData = {
  CODE: "#616161", // dark-grey
  GROUP: "#BFBDB0", // light-grey
  DATA: "#0072B2", // blue
  MEM: "#009E73", // green
  TYPE: "#E69F00", // orange
  MODEL: "#CC79A7", // pink
  UNKNOWN: "#F0E442", // yellow
  CONTROL: "#D55E00", // red orange
  CONTROLDEP: "#56B4E9", // aqua
};

const DetailShapes: Record<string, cytoscape.Css.NodeShape> = {
  CODE: "rectangle",
  DATA: "rectangle",
  LOWLEVEL: "rhomboid",
  LOC: "ellipse",
  RIGHT: "tag",
  LEFT: "tag",
  MODEL: "barrel",
};

type NodeKindMapping = Record<NodeKind, string>;
const NODE_KIND_COLOR_MAP: NodeKindMapping = {
  Alloca: DetailColors.CODE,
  Argument: DetailColors.DATA,
  ArrayType: DetailColors.TYPE,
  ASMBlock: DetailColors.CODE,
  ASMGlobalVariable: DetailColors.MEM,
  ASMInst: DetailColors.CODE,
  BasicType: DetailColors.TYPE,
  Block: DetailColors.CODE,
  Call: DetailColors.CODE,
  CallReturn: DetailColors.MODEL,
  ClassType: DetailColors.TYPE,
  CompositeCachedType: DetailColors.TYPE,
  CompositeType: DetailColors.TYPE,
  Constant: DetailColors.DATA,
  ConstantFp: DetailColors.DATA,
  ConstantInt: DetailColors.DATA,
  ConstantString: DetailColors.DATA,
  ConstantUndef: DetailColors.DATA,
  DataflowSignature: DetailColors.MODEL,
  DerivedType: DetailColors.TYPE,
  DWARFArgument: DetailColors.DATA,
  DWARFLocalVariable: DetailColors.DATA,
  DWARFType: DetailColors.TYPE,
  EnumType: DetailColors.TYPE,
  Function: DetailColors.GROUP,
  GlobalVariable: DetailColors.MEM,
  InputSignature: DetailColors.MODEL,
  Instruction: DetailColors.CODE,
  Invoke: DetailColors.CODE,
  LLVMType: DetailColors.TYPE,
  Load: DetailColors.CODE,
  LocalVariable: DetailColors.MEM,
  MachineBasicBlock: DetailColors.CODE,
  MachineFunction: DetailColors.CODE,
  MachineInstr: DetailColors.CODE,
  Memcpy: DetailColors.CODE,
  MemoryLocation: DetailColors.MEM,
  Memset: DetailColors.CODE,
  Module: DetailColors.CODE,
  OutputSignature: DetailColors.MODEL,
  ParamBinding: DetailColors.MODEL,
  PLTStub: DetailColors.TYPE,
  Resume: DetailColors.CODE,
  Ret: DetailColors.CODE,
  Source: DetailColors.GROUP,
  Store: DetailColors.CODE,
  StructureType: DetailColors.TYPE,
  SubroutineType: DetailColors.TYPE,
  TranslationUnit: DetailColors.CODE,
  UnclassifiedNode: DetailColors.UNKNOWN,
  UnionType: DetailColors.TYPE,
  VTable: DetailColors.TYPE,
};

const NODE_KIND_SHAPE_MAP: NodeKindMapping = {
  Alloca: DetailShapes.CODE,
  Argument: DetailShapes.DATA,
  ArrayType: DetailShapes.LOWLEVEL,
  ASMBlock: DetailShapes.LOWLEVEL,
  ASMGlobalVariable: DetailShapes.LOWLEVEL,
  ASMInst: DetailShapes.LOWLEVEL,
  BasicType: DetailShapes.LOWLEVEL,
  Block: DetailShapes.CODE,
  Call: DetailShapes.CODE,
  CallReturn: DetailShapes.CODE,
  ClassType: DetailShapes.LOWLEVEL,
  CompositeCachedType: DetailShapes.LOWLEVEL,
  CompositeType: DetailShapes.LOWLEVEL,
  Constant: DetailShapes.DATA,
  ConstantFp: DetailShapes.DATA,
  ConstantInt: DetailShapes.DATA,
  ConstantString: DetailShapes.DATA,
  ConstantUndef: DetailShapes.DATA,
  DataflowSignature: DetailShapes.MODEL,
  DerivedType: DetailShapes.LOWLEVEL,
  DWARFArgument: DetailShapes.LOWLEVEL,
  DWARFType: DetailShapes.LOWLEVEL,
  DWARFLocalVariable: DetailShapes.LOWLEVEL,
  EnumType: DetailShapes.LOWLEVEL,
  Function: DetailShapes.CODE,
  GlobalVariable: DetailShapes.DATA,
  InputSignature: DetailShapes.RIGHT,
  Instruction: DetailShapes.CODE,
  Invoke: DetailShapes.CODE,
  LLVMType: DetailShapes.CODE,
  Load: DetailShapes.CODE,
  LocalVariable: DetailShapes.DATA,
  MachineBasicBlock: DetailShapes.LOWLEVEL,
  MachineFunction: DetailShapes.LOWLEVEL,
  MachineInstr: DetailShapes.LOWLEVEL,
  Memcpy: DetailShapes.CODE,
  MemoryLocation: DetailShapes.LOC,
  Memset: DetailShapes.CODE,
  Module: DetailShapes.CODE,
  OutputSignature: DetailShapes.LEFT,
  ParamBinding: DetailShapes.CODE,
  PLTStub: DetailShapes.LOWLEVEL,
  Resume: DetailShapes.CODE,
  Ret: DetailShapes.CODE,
  Source: DetailShapes.CODE,
  Store: DetailShapes.CODE,
  StructureType: DetailShapes.LOWLEVEL,
  SubroutineType: DetailShapes.LOWLEVEL,
  TranslationUnit: DetailShapes.CODE,
  UnclassifiedNode: DetailShapes.CODE,
  UnionType: DetailShapes.LOWLEVEL,
  VTable: DetailShapes.LOWLEVEL,
};

const EDGE_KIND_COLOR_MAP = {
  ValueDefinitionToUse: DetailColors.DATA,
  StoreMemory: DetailColors.DATA,
  LoadMemory: DetailColors.DATA,
  DataflowSignature: DetailColors.DATA,
  DirectDataflowSignature: DetailColors.DATA,
  IndirectDataflowSignature: DetailColors.DATA,
  ControlDataflowSignature: DetailColors.DATA,
  OperandToParamBinding: DetailColors.DATA,
  ParamBindingToArg: DetailColors.DATA,
  ReturnValueToCallReturn: DetailColors.DATA,
  CallReturnToCaller: DetailColors.DATA,

  Callgraph: DetailColors.CONTROL,
  CallToFunction: DetailColors.CONTROL,
  InstructionToSuccessorInstruction: DetailColors.CONTROL,
  DataflowSignatureForCallSite: DetailColors.CONTROL,
  FunctionToEntryInstruction: DetailColors.CONTROL,

  FunctionEntryToControlDependentInstruction: DetailColors.CONTROLDEP,
  TerminatorInstructionToControlDependentInstruction: DetailColors.CONTROLDEP,

  PointsTo: DetailColors.MEM,
  Contains: DetailColors.MEM,
  Subregion: DetailColors.MEM,
  Allocates: DetailColors.MEM,
  MayAlias: DetailColors.MEM,
  MustAlias: DetailColors.MEM,
};

const EDGE_KIND_LINE_MAP = {
  ValueDefinitionToUse: "solid",
  CallReturnToCaller: "solid",
};

const mapByValue = (orig: Record<string, string>): Record<string, string[]> =>
  Object.entries(orig).reduce<Record<string, string[]>>((acc, [kind, key]) => {
    if (acc[key]) {
      acc[key] = acc[key].concat([kind]);
    } else {
      acc[key] = [kind];
    }

    return acc;
  }, {});

const genSelector = (type: string, key: string) => (value: string) =>
  `${type}[${key} = '${value}']`;

const makeShapes = (): Stylesheet[] => {
  const shapes = mapByValue(NODE_KIND_SHAPE_MAP);

  return Object.entries(shapes).map(([shape, kinds]) => ({
    selector: kinds.map(genSelector("node", "node_kind")).join(", "),
    style: {
      shape: shape as cystoscape.Css.NodeShape,
    },
  }));
};

const makeShapeColors = (): Stylesheet[] => {
  const colors = mapByValue(NODE_KIND_COLOR_MAP);

  return Object.entries(colors).map(([color, kinds]) => ({
    selector: kinds.map(genSelector("node", "node_kind")).join(", "),
    style: {
      "background-color": color,
    },
  }));
};

const makeEdgeColors = (): Stylesheet[] => {
  const colors = mapByValue(EDGE_KIND_COLOR_MAP);

  return Object.entries(colors).map(([color, kinds]) => ({
    selector: kinds.map(genSelector("edge", "kind")).join(", "),
    style: {
      "line-color": color,
      "target-arrow-color": color,
    },
  }));
};

const makeEdgeLines = (): Stylesheet[] => {
  const lines = mapByValue(EDGE_KIND_LINE_MAP);

  return Object.entries(lines).map(([line, kinds]) => ({
    selector: kinds.map(genSelector("edge", "node_kind")).join(", "),
    style: {
      "line-style": line as cytoscape.Css.LineStyle,
    },
  }));
};

const baseStylesheet: Stylesheet[] = [
  {
    selector: "node",
    style: {
      content: "data(label)",
      "background-opacity": 0.8,
      "text-wrap": "wrap",
      "text-valign": "top",
      "text-halign": "center",
      "font-family": "Courier, monospaced",
    },
  },
];

export const graphStylesheet: Stylesheet[] = baseStylesheet
  .concat(makeShapes())
  .concat(makeShapeColors())
  .concat([
    {
      selector: "node[node_kind = 'Function']",
      style: {
        "background-opacity": 0.5,
      },
    },
    {
      selector: "edge",
      style: {
        width: 2,
        "line-color": DetailColors.CODE,
        "target-arrow-color": DetailColors.CODE,
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
      },
    },
  ])
  .concat(makeEdgeColors())
  .concat(makeEdgeLines());

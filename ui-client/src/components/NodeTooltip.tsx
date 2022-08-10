import React, { RefObject } from "react";
import { Card, ListGroup, Overlay } from "react-bootstrap";

import type { UiNode, GraphType, NodeKind } from "../lib/api";

import "../styles/NodeTooltip.scss";

type MenuChoices = Record<GraphType, string>;

const MENU_CHOICES: MenuChoices = {
  reverse_dataflow: "Show data flow reaching this node",
  forward_dataflow: "Show data flow from this node",
  reverse_control_flow: "Show control flow reaching this node",
  forward_control_flow: "Show control flow from this node",
  forward_control_dependence: "Show controlled instructions",
  reverse_control_dependence: "Show controlling instructions",
  operands: "Show operands",
  uses: "Show uses",
  callsites: "Show callsites",
  callers: "Show callers",
  callees: "Show callees",
  forward_points_to: "Show pointed to memory locations",
  reverse_points_to: "Show pointers to this memory location",
  forward_points_to_reachable: "Show reachable memory locations",
  reverse_points_to_reachable: "Show pointers reaching this memory location",
  forward_allocation: "Show allocated memory locations",
  reverse_allocation: "Show allocation site",
  forward_memory_subregion: "Show memory subregions",
  reverse_memory_subregion: "Show containing memory regions",
  aliased_memory_locations: "Show aliased memory locations",
  signatures: "Show dataflow and I/O signatures",
};

// NOTE: this is a brittle implementation since we've hard-coded
//       node kinds and the available options here in the client
//       See https://gitlab-ext.galois.com/mate/MATE/-/issues/1467#note_100951
//       for background on the rationale for choosing this route for the
//       initial implementation
const MENU_CHOICES_BY_NODE_KIND: Record<NodeKind, GraphType[]> = {
  Alloca: [
    "reverse_dataflow",
    "forward_dataflow",
    "reverse_control_flow",
    "forward_control_flow",
    "reverse_control_dependence",
    "operands",
    "uses",
    "forward_allocation",
    "forward_points_to",
    "forward_points_to_reachable",
  ],
  Argument: [
    "reverse_dataflow",
    "forward_dataflow",
    "uses",
    "forward_points_to",
    "forward_points_to_reachable",
  ],
  ArrayType: [],
  ASMBlock: [],
  ASMGlobalVariable: [],
  ASMInst: [],
  BasicType: [],
  Block: [
    "reverse_dataflow",
    "forward_dataflow",
    "reverse_control_flow",
    "forward_control_flow",
  ],
  Call: [
    "reverse_dataflow",
    "forward_dataflow",
    "reverse_control_flow",
    "forward_control_flow",
    "reverse_control_dependence",
    "forward_control_dependence",
    "operands",
    "uses",
    "forward_allocation",
    "forward_points_to",
    "forward_points_to_reachable",
    "callees",
    "signatures",
  ],
  CallReturn: ["reverse_dataflow", "forward_dataflow", "callsites"],
  ClassType: [],
  CompositeCachedType: [],
  CompositeType: [],
  Constant: ["reverse_dataflow", "forward_dataflow"],
  ConstantFp: ["reverse_dataflow", "forward_dataflow"],
  ConstantInt: ["reverse_dataflow", "forward_dataflow"],
  ConstantString: ["reverse_dataflow", "forward_dataflow"],
  ConstantUndef: ["reverse_dataflow", "forward_dataflow"],
  DataflowSignature: [
    "reverse_dataflow",
    "forward_dataflow",
    "callsites",
    "callers",
  ],
  DerivedType: [],
  DWARFArgument: [],
  DWARFLocalVariable: [],
  DWARFType: [],
  EnumType: [],
  Function: [
    "forward_dataflow",
    "forward_control_flow",
    "forward_control_dependence",
    "callsites",
    "callers",
    "callees",
    "signatures",
    "uses",
  ],
  GlobalVariable: ["reverse_dataflow", "forward_dataflow"],
  InputSignature: [
    "reverse_dataflow",
    "forward_dataflow",
    "callsites",
    "callers",
  ],
  Instruction: [
    "reverse_dataflow",
    "forward_dataflow",
    "reverse_control_flow",
    "forward_control_flow",
    "reverse_control_dependence",
    "forward_control_dependence",
    "operands",
    "uses",
    "forward_allocation",
    "forward_points_to",
    "forward_points_to_reachable",
  ],
  Invoke: [
    "reverse_dataflow",
    "forward_dataflow",
    "reverse_control_flow",
    "forward_control_flow",
    "reverse_control_dependence",
    "forward_control_dependence",
    "operands",
    "uses",
    "forward_allocation",
    "forward_points_to",
    "forward_points_to_reachable",
    "callees",
    "signatures",
  ],
  LLVMType: [],
  Load: [
    "reverse_dataflow",
    "forward_dataflow",
    "reverse_control_flow",
    "forward_control_flow",
    "reverse_control_dependence",
    "forward_control_dependence",
    "operands",
    "uses",
    "forward_points_to",
    "forward_points_to_reachable",
  ],
  LocalVariable: [
    "reverse_dataflow",
    "forward_dataflow",
    "forward_points_to",
    "forward_points_to_reachable",
  ],
  MachineBasicBlock: [],
  MachineFunction: [],
  MachineInstr: [],
  Memcpy: [
    "reverse_dataflow",
    "forward_dataflow",
    "reverse_control_flow",
    "forward_control_flow",
    "reverse_control_dependence",
    "forward_control_dependence",
    "operands",
    "uses",
    "forward_points_to",
    "forward_points_to_reachable",
    "callees",
    "signatures",
  ],
  MemoryLocation: [
    "reverse_dataflow",
    "forward_dataflow",
    "reverse_allocation",
    "forward_memory_subregion",
    "reverse_memory_subregion",
    "aliased_memory_locations",
    "forward_points_to",
    "forward_points_to_reachable",
    "reverse_points_to",
    "reverse_points_to_reachable",
  ],
  Memset: [
    "reverse_dataflow",
    "forward_dataflow",
    "reverse_control_flow",
    "forward_control_flow",
    "reverse_control_dependence",
    "forward_control_dependence",
    "operands",
    "uses",
    "forward_points_to",
    "forward_points_to_reachable",
    "callees",
    "signatures",
  ],
  Module: [],
  OutputSignature: [
    "reverse_dataflow",
    "forward_dataflow",
    "callsites",
    "callers",
  ],
  ParamBinding: ["reverse_dataflow", "forward_dataflow", "callsites"],
  PLTStub: [],
  Resume: [
    "reverse_dataflow",
    "forward_dataflow",
    "reverse_control_flow",
    "forward_control_flow",
    "reverse_control_dependence",
    "forward_control_dependence",
    "operands",
    "uses",
    "forward_points_to",
    "forward_points_to_reachable",
  ],
  Ret: [
    "reverse_dataflow",
    "forward_dataflow",
    "reverse_control_flow",
    "forward_control_flow",
    "reverse_control_dependence",
    "forward_control_dependence",
    "operands",
  ],
  Source: [],
  Store: [
    "reverse_dataflow",
    "forward_dataflow",
    "reverse_control_flow",
    "forward_control_flow",
    "reverse_control_dependence",
    "forward_control_dependence",
    "operands",
    "uses",
    "forward_points_to",
    "forward_points_to_reachable",
  ],
  StructureType: [],
  SubroutineType: [],
  TranslationUnit: [],
  UnclassifiedNode: [],
  UnionType: [],
  VTable: [],
};

interface NodeTooltipProps {
  targetRef: () => HTMLElement | RefObject<HTMLElement> | null;
  x: number;
  y: number;
  onAddNodeCard: () => void;
  onMouseleave: () => void;
  onSetSink: () => void;
  onSetSource: () => void;
  onSubmit: (choice: GraphType) => void;
  show: boolean;
  node?: UiNode;
}

export const NodeTooltip: React.FC<NodeTooltipProps> = ({
  targetRef,
  node,
  x,
  y,
  onAddNodeCard,
  onMouseleave,
  onSetSink,
  onSetSource,
  onSubmit,
  show,
}) => {
  const nodeChoices = node ? MENU_CHOICES_BY_NODE_KIND[node.node_kind] : [];

  return nodeChoices.length > 0 ? (
    <Overlay target={targetRef} show={show} placement="right">
      {({ ref }) => {
        return (
          <div
            ref={ref}
            className="NodeTooltip"
            style={{
              left: x,
              top: y,
            }}
            data-test-id="tooltip"
            onMouseLeave={onMouseleave}
          >
            <Card>
              <ListGroup variant="flush">
                {}
                {nodeChoices.map((key, i) => (
                  <ListGroup.Item
                    key={`${key}-${i}`}
                    onClick={() => onSubmit(key as GraphType)}
                  >
                    {MENU_CHOICES[key]}
                  </ListGroup.Item>
                ))}
                <ListGroup.Item key="set-as-source" onClick={onSetSource}>
                  Set as source
                </ListGroup.Item>
                <ListGroup.Item key="set-as-sink" onClick={onSetSink}>
                  Set as sink
                </ListGroup.Item>
                <ListGroup.Item key="add-node-card" onClick={onAddNodeCard}>
                  Add card for node
                </ListGroup.Item>
              </ListGroup>
            </Card>
          </div>
        );
      }}
    </Overlay>
  ) : null;
};

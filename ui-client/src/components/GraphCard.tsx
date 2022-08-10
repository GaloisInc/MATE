import React, { useCallback, useState, ReactNode, ChangeEvent } from "react";
import { Button, Card, Container, Form } from "react-bootstrap";
import { RiFocus3Line, RiDeleteBin6Line } from "react-icons/ri";
import { BiCommentAdd, BiHide } from "react-icons/bi";
import { MdClose, MdEdit } from "react-icons/md";

import { ToggleSwitch } from "./ToggleSwitch";
import {
  displayGraphType,
  UiGraph,
  UiGraphSlice,
  UiNodeGraph,
} from "../lib/api";
import { GraphId, NodeId } from "./Graph";

import "../styles/GraphCard.scss";
import { FlowFinderAnnotation } from "../lib/api/snapshots";

interface AnnotationEditorProps {
  annotation?: FlowFinderAnnotation;
  onSave?: (a: string, c: number) => void;
  onUpdate?: (a: FlowFinderAnnotation) => void;
  onCancel: () => void;
}

const AnnotationEditor = ({
  annotation,
  onSave,
  onUpdate,
  onCancel,
}: AnnotationEditorProps) => {
  const [value, setValue] = useState(annotation?.annotation ?? "");

  const onChange = useCallback(
    (e: ChangeEvent<HTMLTextAreaElement>) => setValue(e.target.value),
    []
  );
  const onSaveHandler = useCallback(() => {
    if (annotation) {
      onUpdate?.({ ...annotation, annotation: value });
    } else {
      onSave?.(value, Date.now());
    }
  }, [annotation, onSave, onUpdate, value]);

  return (
    <>
      {annotation && new Date(annotation.createdAt).toLocaleString()}
      <Form.Control as="textarea" onChange={onChange} value={value} />
      <Button onClick={onSaveHandler} className="mt-1" size="sm">
        Save
      </Button>
      <Button
        onClick={onCancel}
        className="mt-1 mx-1"
        size="sm"
        variant="secondary"
      >
        Cancel
      </Button>
    </>
  );
};

interface AnnotationsProps {
  annotations: FlowFinderAnnotation[];
  onSave: (annotation: string, createdAt: number) => void;
  onUpdate: (annotation: FlowFinderAnnotation) => void;
}

const Annotations = ({ annotations, onSave, onUpdate }: AnnotationsProps) => {
  const [isEditorVisible, setIsEditorVisible] = useState(false);
  const [currAnnotationIdx, setCurrAnnotationIdx] = useState(-1);

  const onCreateAnnotation = useCallback(
    (a: string, c: number) => {
      onSave(a, c);
      setIsEditorVisible(false);
      setCurrAnnotationIdx(-1);
    },
    [onSave]
  );

  const onUpdateAnnotation = useCallback(
    (a: FlowFinderAnnotation) => {
      onUpdate(a);
      setIsEditorVisible(false);
      setCurrAnnotationIdx(-1);
    },
    [onUpdate]
  );

  const onOpenEditor = useCallback(() => setIsEditorVisible(true), []);
  const onCancelUpdate = useCallback(() => {
    setIsEditorVisible(false);
    setCurrAnnotationIdx(-1);
  }, []);

  return (
    <Container className="Annotations m-0 p-0">
      <h5>
        Annotations: <BiCommentAdd className="add" onClick={onOpenEditor} />
      </h5>
      {annotations.map((a, i) => (
        <div key={`${a.graphId}-${a.createdAt}`} className="annotation">
          {currAnnotationIdx === i ? (
            <AnnotationEditor
              annotation={a}
              onUpdate={onUpdateAnnotation}
              onCancel={onCancelUpdate}
            />
          ) : (
            <>
              <MdEdit className="add" onClick={() => setCurrAnnotationIdx(i)} />
              <span>
                {new Date(a.createdAt).toLocaleString()} - {a.annotation}
              </span>
            </>
          )}
        </div>
      ))}
      {isEditorVisible && (
        <AnnotationEditor
          onSave={onCreateAnnotation}
          onCancel={onCancelUpdate}
        />
      )}
    </Container>
  );
};

interface GraphCardProps {
  children: ReactNode;
  enabled: boolean;
  graphId: string;
  label: string;
  onAddAnnotation: (id: GraphId, annotation: string, createdAt: number) => void;
  onUpdateAnnotation: (annotation: FlowFinderAnnotation) => void;
  onClick: (id: GraphId) => void;
  onDelete: (id: GraphId) => void;
  onMouseEnter: (id: GraphId) => void;
  onMouseLeave: (id: GraphId) => void;
  onToggleEnabled: (id: GraphId) => void;
  onToggleAnalysis?: (id: GraphId) => void;
  isInAnalysisMode?: boolean;
  annotations?: FlowFinderAnnotation[];
}

interface GraphCardComposition {
  GraphData: React.FC<GraphDataProps>;
  SliceData: React.FC<SliceDataProps>;
  NodeData: React.FC<GraphNodeDataProps>;
}

// TODO: consider whether we need a GraphCard.Header subcomponent where the addition of toggles is controlled?
export const GraphCard: React.FC<GraphCardProps> & GraphCardComposition = ({
  annotations = [],
  children,
  enabled,
  graphId,
  isInAnalysisMode,
  label,
  onAddAnnotation,
  onUpdateAnnotation,
  onClick,
  onDelete,
  onMouseEnter,
  onMouseLeave,
  onToggleEnabled,
  onToggleAnalysis,
}) => {
  const graphToggleId = `graph-toggle-${graphId}`;
  const graphAnalyzeId = `graph-analyze-${graphId}`;

  const handleClick = useCallback(() => onClick(graphId), [onClick, graphId]);

  const handleDelete = useCallback(
    () => onDelete(graphId),
    [onDelete, graphId]
  );

  const handleMouseEnter = useCallback(
    () => onMouseEnter(graphId),
    [onMouseEnter, graphId]
  );

  const handleMouseLeave = useCallback(
    () => onMouseLeave(graphId),
    [onMouseLeave, graphId]
  );

  const handleToggle = useCallback(
    () => onToggleEnabled(graphId),
    [onToggleEnabled, graphId]
  );

  const handleAnalysisToggle = useCallback(
    () => onToggleAnalysis?.(graphId),
    [onToggleAnalysis, graphId]
  );

  const handleAddAnnotation = useCallback(
    (annotation: string, createdAt: number) => {
      onAddAnnotation(graphId, annotation, createdAt);
    },
    [graphId, onAddAnnotation]
  );

  const handleUpdateAnnotation = useCallback(
    (a: FlowFinderAnnotation) => onUpdateAnnotation(a),
    [onUpdateAnnotation]
  );

  return (
    <div
      className="GraphCard mb-3"
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <Card>
        <Card.Header className="d-flex justify-content-between">
          <div className="d-flex mr-auto text-left align-items-center">
            <MdClose className="close" size={25} onClick={handleDelete} />
            <h2>
              {label} - "{graphId}"
            </h2>
          </div>
          <div className="d-flex flex-row-reverse ml-auto text-right">
            <ToggleSwitch
              id={graphToggleId}
              onToggle={handleToggle}
              checked={enabled}
              label="enabled"
            />
            {onToggleAnalysis && (
              <ToggleSwitch
                id={graphAnalyzeId}
                onToggle={handleAnalysisToggle}
                checked={isInAnalysisMode}
                label="analyze"
              />
            )}
          </div>
        </Card.Header>
        <Card.Body>
          {children}
          <Annotations
            annotations={annotations}
            onSave={handleAddAnnotation}
            onUpdate={handleUpdateAnnotation}
          />
        </Card.Body>
      </Card>
    </div>
  );
};

export interface AnalysisNode {
  id: string;
  action: "focus" | "avoid" | "";
}

interface SliceDataProps {
  sliceData: UiGraphSlice;
  analysisNodes: Record<string, AnalysisNode>;
  graphId: GraphId;
  onAnalyze: (id: GraphId) => void;
  onDeleteNode: (id: NodeId) => void;
  onToggleFocus: (id: NodeId) => void;
  onToggleAvoid: (id: NodeId) => void;
  isInAnalysisMode?: boolean;
}

const SliceData: React.FC<SliceDataProps> = ({
  analysisNodes,
  graphId,
  sliceData,
  isInAnalysisMode,
  onAnalyze,
  onDeleteNode,
  onToggleAvoid,
  onToggleFocus,
}) => {
  const aNodes = isInAnalysisMode
    ? analysisNodes
    : {
        ...sliceData.focusNodeIds?.reduce(
          (acc, id) => ({
            ...acc,
            [id]: { id, action: "focus" },
          }),
          {}
        ),
        ...sliceData.avoidNodeIds?.reduce(
          (acc, id) => ({
            ...acc,
            [id]: { id, action: "avoid" },
          }),
          {}
        ),
      };

  const hasNoActionNode =
    Object.values(aNodes).filter((n) => n.action === "").length > 0;

  const { source, sink, kind } = sliceData;
  const getLabel = function (node_id: string) {
    const node = sliceData.nodes.find((elem) => elem.node_id === node_id);
    if (node === undefined) {
      return "Unknown";
    } else {
      return node.label;
    }
  };
  const source_label = getLabel(source);
  const sink_label = getLabel(sink);

  return (
    <div className="GraphCardSliceData">
      <h5>Source:</h5>
      <span className="key">
        {source_label}
        <br />({source})
      </span>
      <h5>Sink:</h5>
      <span className="key">
        {sink_label}
        <br />({sink})
      </span>
      <h5>Kind:</h5>
      <span className="key">{displayGraphType(kind)}</span>
      <div className="analysis d-flex justify-content-between">
        <h5>Focus/Avoid Nodes:</h5>
        <Button
          size="sm"
          variant="light"
          onClick={() => onAnalyze(graphId)}
          disabled={!isInAnalysisMode || hasNoActionNode}
        >
          Run Analysis
        </Button>
      </div>
      <ul>
        {Object.entries(aNodes).map(([id, n], i) => (
          <li key={`focus-avoid-${id}`} className="d-flex align-items-center">
            <BiHide
              className={`avoid ${n.action === "avoid" ? "selected" : ""} ${
                isInAnalysisMode || "inactive"
              }`}
              onClick={() => isInAnalysisMode && onToggleAvoid(n.id)}
            />
            <RiFocus3Line
              className={`focus ${n.action === "focus" ? "selected" : ""} ${
                isInAnalysisMode || "inactive"
              }`}
              onClick={() => isInAnalysisMode && onToggleFocus(n.id)}
            />
            {getLabel(n.id)}
            <br />({n.id})
            {isInAnalysisMode && (
              <RiDeleteBin6Line
                className={`delete ${isInAnalysisMode || "inactive"}`}
                onClick={() => isInAnalysisMode && onDeleteNode(n.id)}
              />
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};

GraphCard.SliceData = SliceData;

interface GraphDataProps {
  graph: UiGraph;
}

const GraphData: React.FC<GraphDataProps> = ({ graph }) => {
  const getLabel = function (node_id: string) {
    const node = graph.nodes.find((elem) => elem.node_id === node_id);
    if (node === undefined) {
      return "Unknown";
    } else {
      return node.label;
    }
  };

  return (
    <>
      <h5>Origin Nodes:</h5>
      <ul>
        {graph.originNodeIds.map((id) => (
          <li key={`origin-node-${id}`}>
            {getLabel(id)}
            <br />({id})
          </li>
        ))}
      </ul>
      <h5>Kind:</h5>
      <span className="key">{displayGraphType(graph.kind)}</span>
    </>
  );
};

GraphCard.GraphData = GraphData;

interface GraphNodeDataProps {
  nodeGraph: UiNodeGraph;
}

const NodeData: React.FC<GraphNodeDataProps> = ({ nodeGraph }) => {
  const node = nodeGraph.nodes[0];
  return (
    <>
      <h5>Node:</h5>
      <span className="key">
        {node.label}
        <br />({node.node_id})
      </span>
      <h5>Kind:</h5>
      <span className="key">{node.node_kind}</span>
    </>
  );
};

GraphCard.NodeData = NodeData;

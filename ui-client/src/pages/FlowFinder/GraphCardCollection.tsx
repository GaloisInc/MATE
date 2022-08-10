import { Alert } from "react-bootstrap";
import { GoAlert } from "react-icons/go";

import { GraphId, NodeId } from "../../components/Graph";
import { GraphCard } from "../../components/GraphCard";

import type {
  AnalysisNodesCache,
  GraphCache,
  GraphSliceCache,
  NodeCache,
} from "../../hooks/useFlowFinder";

import type { UiGraph, UiGraphSlice, UiNodeGraph } from "../../lib/api";
import { FlowFinderAnnotation } from "../../lib/api/snapshots";

interface GraphCardCollectionProps {
  annotationsByGraphId: Record<string, FlowFinderAnnotation[]>;
  collection: GraphCache | GraphSliceCache | NodeCache;
  label: "Node" | "Graph" | "Slice";
  onAddAnnotation: (id: GraphId, annotation: string, createdAt: number) => void;
  onUpdateAnnotation: (annotation: FlowFinderAnnotation) => void;
  onClick: (id: GraphId) => void;
  onDelete: (id: GraphId) => void;
  onMouseEnter: (id: GraphId) => void;
  onMouseLeave: (id: GraphId) => void;
  onToggleEnabled: (id: GraphId) => void;
  hiddenGraphIds: GraphId[];
  analysisGraphId?: GraphId;
  analysisNodesById?: AnalysisNodesCache;
  onAnalyze?: (id: GraphId) => void;
  onDeleteAnalysisNode?: (id: NodeId) => void;
  onDeleteNode?: (id: NodeId) => void;
  onToggleAnalysis?: (id: GraphId) => void;
  onToggleAvoidNode?: (id: NodeId) => void;
  onToggleFocusNode?: (id: NodeId) => void;
}

export const GraphCardCollection: React.FC<GraphCardCollectionProps> = ({
  analysisGraphId,
  analysisNodesById,
  annotationsByGraphId,
  collection,
  hiddenGraphIds,
  label,
  onAddAnnotation,
  onUpdateAnnotation,
  onAnalyze,
  onClick,
  onDelete,
  onDeleteAnalysisNode,
  onMouseEnter,
  onMouseLeave,
  onToggleEnabled,
  onToggleAnalysis,
  onToggleAvoidNode,
  onToggleFocusNode,
}) => {
  return (
    <>
      {Object.entries(collection).map(([key, graph]) => {
        const enabled =
          !hiddenGraphIds.includes(key) || (analysisGraphId ? true : false);

        const isInAnalysisMode =
          analysisGraphId !== undefined ? key === analysisGraphId : false;

        // TODO: this is the first pass at simplifying the logic for generating cards
        //       however, this "emptyFn" is only here because only the <GraphCard.SliceData>
        //       requires some handlers be passed, so they are optional
        //       There has to be a better way to do this...
        const emptyFn = (id: string) =>
          console.log(`No handler provided to process(${id})`);

        const isEmptyGraph = label !== "Node" && graph.nodes.length <= 1;

        const annotations = annotationsByGraphId[key] ?? [];

        return (
          <GraphCard
            annotations={annotations}
            enabled={enabled}
            graphId={key}
            isInAnalysisMode={isInAnalysisMode}
            key={`graph-card-${key}`}
            label={label}
            onAddAnnotation={onAddAnnotation}
            onUpdateAnnotation={onUpdateAnnotation}
            onClick={() => onClick(key)}
            onDelete={() => onDelete(key)}
            onMouseEnter={onMouseEnter}
            onMouseLeave={onMouseLeave}
            onToggleEnabled={onToggleEnabled}
            {...(onToggleAnalysis ? { onToggleAnalysis } : null)}
          >
            {isEmptyGraph && (
              <Alert key={`alert-${key}`} variant="warning">
                <GoAlert />
                <div>
                  <p>This graph is empty.</p>
                  <p className="m-0">
                    There were no nodes or edges returned for this query.
                  </p>
                </div>
              </Alert>
            )}
            {(() => {
              switch (label) {
                case "Node":
                  return (
                    <GraphCard.NodeData nodeGraph={graph as UiNodeGraph} />
                  );
                case "Graph":
                  return <GraphCard.GraphData graph={graph as UiGraph} />;
                case "Slice":
                  return (
                    <GraphCard.SliceData
                      analysisNodes={analysisNodesById ?? {}}
                      graphId={key}
                      sliceData={graph as UiGraphSlice}
                      isInAnalysisMode={isInAnalysisMode}
                      onAnalyze={onAnalyze ?? emptyFn}
                      onDeleteNode={onDeleteAnalysisNode ?? emptyFn}
                      onToggleAvoid={onToggleAvoidNode ?? emptyFn}
                      onToggleFocus={onToggleFocusNode ?? emptyFn}
                    />
                  );
                default:
                  return null;
              }
            })()}
          </GraphCard>
        );
      })}
    </>
  );
};

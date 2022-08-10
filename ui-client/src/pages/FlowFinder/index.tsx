import { marked } from "marked";
import { useParams } from "react-router";
import { CardGroup } from "react-bootstrap";

import { Background } from "../../components/Background";
import { Insight } from "../../components/Insight";
import { ErrorAlert } from "../../components/ErrorAlert";
import { Filters } from "../../components/Filters";
import { Graph } from "../../components/Graph";
import { NodeSelector } from "../../components/NodeSelector";
import { NodeTooltip } from "../../components/NodeTooltip";
import { SliceSelector } from "../../components/SliceSelector";
import { Page } from "../../components/Page";
import { PanelGrid } from "../../components/PanelGrid";
import { SnapshotSaver } from "../../components/SnapshotSaver";
import { NotebookButton } from "../../components/NotebookButton";
import { GraphCardCollection } from "./GraphCardCollection";

import { useFlowFinder } from "../../hooks/useFlowFinder";
import type {
  FlowFinderEdgeData,
  FlowFinderNodeData,
} from "../../hooks/useFlowFinder";

import {
  graphStylesheet,
  DetailColors,
} from "../../components/graph-stylesheet";

import "../../styles/FlowFinder.scss";

interface FlowFinderUrlParams {
  buildId: string;
  poiId?: string;
  snapshotId?: string;
}

export const FlowFinder: React.FC = () => {
  const { buildId, poiId, snapshotId } = useParams<FlowFinderUrlParams>();

  const {
    // state
    analysisGraphId,
    analysisNodesById,
    annotationsByGraphId,
    background,
    centerGraphId,
    contextNode,
    error,
    filters,
    functionNodes,
    binaryName,
    graphCache,
    graphDimensions,
    graphSliceCache,
    graphTargetRef,
    hiddenGraphIds,
    hiddenNodeIds,
    highlightedGraphId,
    insight,
    isLoading,
    loadingMessage,
    lrgLayoutConfig,
    mergedGraphs,
    mouseCoord,
    nodeCache,
    pauseGraphResize,
    shouldShowContextMenu,
    sinkId,
    sourceId,
    stdLayoutConfig,

    // event handlers
    onAddAnnotation,
    onUpdateAnnotation,
    onAddNodeCard,
    onAnalyze,
    onCenterGraph,
    onContextMenuLeave,
    onContextNodeDeselect,
    onContextNodeSelect,
    onDeleteAnalysisNode,
    onDeleteGraph,
    onDeleteNodeGraph,
    onDeleteSlice,
    onMouseEnter,
    onMouseLeave,
    onNodeSelection,
    onSaveSnapshot,
    onSetSinkId,
    onSetSourceId,
    onSubmitNodeSelection,
    onToggleAnalysis,
    onToggleAvoidNode,
    onToggleFocusNode,
    onToggleGraph,
    pauseGraphResizing,
    setFilters,
    setHighlightedGraphId,
    setNodeId,
    setPanelDimensions,
    setSliceCriteria,
    unPauseGraphResizing,
  } = useFlowFinder({ buildId, poiId, snapshotId });

  return (
    <Page
      className="FlowFinder"
      buildId={buildId}
      binaryName={binaryName}
      isLoading={isLoading}
      loadingMessage={loadingMessage}
    >
      {error && <ErrorAlert errors={[error]} />}
      <PanelGrid
        onDragEnd={unPauseGraphResizing}
        onDragStart={pauseGraphResizing}
        onResize={setPanelDimensions}
      >
        <PanelGrid.GraphWindow>
          <Graph<FlowFinderNodeData, FlowFinderEdgeData, HTMLDivElement>
            centerGraphId={centerGraphId}
            focusGraphId={analysisGraphId}
            graphs={mergedGraphs}
            hiddenGraphIds={hiddenGraphIds}
            hiddenNodeIds={hiddenNodeIds}
            highlightedGraphId={highlightedGraphId}
            keyData={DetailColors}
            layoutConfig={stdLayoutConfig}
            largeGraphFallbackLayoutConfig={lrgLayoutConfig}
            onContextNodeSelect={onContextNodeSelect}
            onContextNodeDeselect={onContextNodeDeselect}
            onNodeSelection={onNodeSelection}
            pauseLayout={isLoading}
            pauseResize={pauseGraphResize}
            ref={graphTargetRef}
            style={graphDimensions}
            stylesheets={graphStylesheet}
          />
          <NodeTooltip
            onAddNodeCard={onAddNodeCard}
            onMouseleave={onContextMenuLeave}
            onSetSink={onSetSinkId}
            onSetSource={onSetSourceId}
            onSubmit={onSubmitNodeSelection}
            targetRef={() => graphTargetRef.current}
            node={contextNode}
            show={shouldShowContextMenu}
            x={mouseCoord.x}
            y={mouseCoord.y}
          />
        </PanelGrid.GraphWindow>
        <PanelGrid.CardWindow>
          <CardGroup>
            <GraphCardCollection
              annotationsByGraphId={annotationsByGraphId}
              collection={graphSliceCache}
              label="Slice"
              analysisNodesById={analysisNodesById}
              analysisGraphId={analysisGraphId}
              hiddenGraphIds={hiddenGraphIds}
              onAddAnnotation={onAddAnnotation}
              onUpdateAnnotation={onUpdateAnnotation}
              onClick={onCenterGraph}
              onDelete={onDeleteSlice}
              onMouseEnter={onMouseEnter}
              onMouseLeave={onMouseLeave}
              onToggleEnabled={onToggleGraph}
              onToggleAnalysis={onToggleAnalysis}
              onAnalyze={onAnalyze}
              onDeleteAnalysisNode={onDeleteAnalysisNode}
              onToggleFocusNode={onToggleFocusNode}
              onToggleAvoidNode={onToggleAvoidNode}
            />
            <GraphCardCollection
              annotationsByGraphId={annotationsByGraphId}
              collection={graphCache}
              hiddenGraphIds={hiddenGraphIds}
              label="Graph"
              onAddAnnotation={onAddAnnotation}
              onUpdateAnnotation={onUpdateAnnotation}
              onClick={onCenterGraph}
              onDelete={onDeleteGraph}
              onMouseEnter={setHighlightedGraphId}
              onMouseLeave={() => setHighlightedGraphId(undefined)}
              onToggleEnabled={onToggleGraph}
            />
            <GraphCardCollection
              annotationsByGraphId={annotationsByGraphId}
              collection={nodeCache}
              hiddenGraphIds={hiddenGraphIds}
              label="Node"
              onAddAnnotation={onAddAnnotation}
              onUpdateAnnotation={onUpdateAnnotation}
              onClick={onCenterGraph}
              onDelete={onDeleteNodeGraph}
              onMouseEnter={setHighlightedGraphId}
              onMouseLeave={() => setHighlightedGraphId(undefined)}
              onToggleEnabled={onToggleGraph}
            />
          </CardGroup>
        </PanelGrid.CardWindow>
        <PanelGrid.RightSidebar>
          <NotebookButton binaryName={binaryName} buildId={buildId} size="sm" />
          <SnapshotSaver onSaveSnapshot={onSaveSnapshot} />
          <Filters onSelect={setFilters} initialChoices={filters} />
          <NodeSelector fnNodes={functionNodes} onSelect={setNodeId} />
          <SliceSelector
            initialSinkId={sinkId}
            initialSourceId={sourceId}
            onSelect={setSliceCriteria}
          />
          <Insight>
            {/* WARNING: The insight text comes from us, so we trust it.

                We should probably use DOMPurify to make this even safer.
             */}
            <div
              dangerouslySetInnerHTML={{ __html: marked.parse(insight ?? "") }}
            />
          </Insight>
          <Background text={background} />
        </PanelGrid.RightSidebar>
      </PanelGrid>
    </Page>
  );
};

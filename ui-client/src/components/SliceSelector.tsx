import React, { useCallback, useEffect, useState, ChangeEvent } from "react";
import { Button, Card, Form } from "react-bootstrap";

import type { GraphType, GraphSliceApiParams } from "../lib/api";

import "../styles/SliceSelector.scss";

export type SliceSelectionCriteria = Omit<GraphSliceApiParams, "build_id">;

interface SliceSelectorProps {
  onSelect: (criteria: SliceSelectionCriteria) => void;
  initialSinkId?: string;
  initialSourceId?: string;
}

export const SliceSelector: React.FC<SliceSelectorProps> = ({
  initialSinkId,
  initialSourceId,
  onSelect,
}) => {
  const [sourceId, setSourceId] = useState<string | undefined>(initialSinkId);
  const [sinkId, setSinkId] = useState<string | undefined>(initialSourceId);
  const [graphType, setGraphType] = useState<GraphType | null>(null);

  useEffect(() => {
    setSinkId(initialSinkId);
    setSourceId(initialSourceId);
  }, [initialSinkId, initialSourceId]);

  const onSetSinkId = useCallback(
    ({ target: { value } }: ChangeEvent<HTMLInputElement>) => setSinkId(value),
    [setSinkId]
  );

  const onSetSourceId = useCallback(
    ({ target: { value } }: ChangeEvent<HTMLInputElement>) =>
      setSourceId(value),
    [setSourceId]
  );

  const onSetDataflowGraphType = useCallback(
    () => setGraphType("forward_dataflow"),
    [setGraphType]
  );

  const onSetControlflowGraphType = useCallback(
    () => setGraphType("forward_control_flow"),
    [setGraphType]
  );

  const onSetControlDependenceGraphType = useCallback(
    () => setGraphType("reverse_control_dependence"),
    [setGraphType]
  );

  const onSetCallGraphGraphType = useCallback(
    () => setGraphType("callees"),
    [setGraphType]
  );

  const submitHandler = useCallback(() => {
    if (sourceId !== undefined && sinkId !== undefined && graphType !== null) {
      onSelect({
        source_id: sourceId,
        sink_id: sinkId,
        kind: graphType,
      });
      setSourceId(undefined);
      setSinkId(undefined);
      setGraphType(null);
    }
  }, [sourceId, sinkId, graphType, onSelect]);

  return (
    <Card className="SliceSelector p-2 mt-2">
      <Form>
        <Form.Control
          type="input"
          placeholder="Enter ID source Node"
          value={sourceId === undefined ? "" : sourceId}
          onChange={onSetSourceId}
        />
        <Form.Control
          className="mt-2"
          type="input"
          placeholder="Enter ID sink Node"
          value={sinkId === undefined ? "" : sinkId}
          onChange={onSetSinkId}
        />
        <Form.Row className="mt-2 d-flex justify-content-between">
          <div>
            <Form.Check
              label="data flow between"
              name="graph-type"
              type="radio"
              id="graph-type-dataflow"
              checked={graphType === "forward_dataflow"}
              onChange={onSetDataflowGraphType}
            />
            <Form.Check
              label="control flow between"
              name="graph-type"
              type="radio"
              id="graph-type-control-flow"
              checked={graphType === "forward_control_flow"}
              onChange={onSetControlflowGraphType}
            />
          </div>
          <div>
            <Form.Check
              label="mutual controlling instructions"
              name="graph-type"
              type="radio"
              id="graph-type-control-dependence"
              checked={graphType === "reverse_control_dependence"}
              onChange={onSetControlDependenceGraphType}
            />
            <Form.Check
              label="mutual call graph"
              name="graph-type"
              type="radio"
              id="graph-type-call-graph"
              checked={graphType === "callees"}
              onChange={onSetCallGraphGraphType}
            />
          </div>
        </Form.Row>
        <Form.Group className="d-flex flex-row-reverse mt-2">
          <Button
            className="float-right"
            size="sm"
            variant="primary"
            type="button"
            disabled={
              sourceId === undefined ||
              sinkId === undefined ||
              graphType === null
            }
            onClick={submitHandler}
          >
            Create New Slice
          </Button>
        </Form.Group>
      </Form>
    </Card>
  );
};

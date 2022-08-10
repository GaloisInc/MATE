import React, { useCallback, useEffect, useState, ChangeEvent } from "react";
import { Button, Card, Form } from "react-bootstrap";

import { FunctionSelector } from "./FunctionSelector";
import type { FlowFinderNode } from "../hooks/useFlowFinder";

import "react-bootstrap-typeahead/css/Typeahead.css";
import "../styles/NodeSelector.scss";

interface NodeSelectorProps {
  onSelect: (nodeId: string) => void;
  fnNodes?: FlowFinderNode[];
}

export const NodeSelector: React.FC<NodeSelectorProps> = ({
  fnNodes,
  onSelect,
}) => {
  const [nodeId, setNodeId] = useState<string | undefined>(undefined);
  const [fnNodeId, setFnNodeId] = useState<string | undefined>(undefined);
  const [nodeSelected, setNodeSelected] = useState(false);

  useEffect(() => {
    setNodeSelected(nodeId !== undefined || fnNodeId !== undefined);
  }, [nodeId, fnNodeId]);

  const handleSubmit = useCallback(() => {
    if (nodeId !== undefined) {
      setNodeId(undefined);
      onSelect(nodeId);
    } else if (fnNodeId !== undefined) {
      setFnNodeId(undefined);
      onSelect(fnNodeId);
    }
  }, [fnNodeId, nodeId, onSelect]);

  const handleNodeIdChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setNodeId(e.target.value);
    setFnNodeId(undefined);
  }, []);

  const handleFnNodeChange = useCallback((selected: FlowFinderNode[]) => {
    if (selected.length > 0) {
      setNodeId(undefined);
      setFnNodeId(selected[0].id);
    }
  }, []);

  return (
    <Card className="NodeSelector p-2 mt-2">
      <Form>
        <Form.Control
          type="input"
          placeholder="Enter ID of Node to add"
          value={nodeId === undefined ? "" : nodeId}
          onChange={handleNodeIdChange}
        />
        {fnNodes && (
          <FunctionSelector
            functionNodes={fnNodes}
            label="Or Select a Function Node to Start..."
            onChange={handleFnNodeChange}
            selectedId={fnNodeId}
          />
        )}
        <Form.Group className="d-flex flex-row-reverse mt-2">
          <Button
            className="float-right"
            size="sm"
            variant="primary"
            type="button"
            onClick={handleSubmit}
            disabled={!nodeSelected}
          >
            Add Node
          </Button>
        </Form.Group>
      </Form>
    </Card>
  );
};

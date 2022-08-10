import { useCallback, useState } from "react";
import type { ChangeEvent } from "react";
import { Button, Col, Form, Row } from "react-bootstrap";
import { v4 as uuidv4 } from "uuid";

import { ToggleSwitch } from "../../components/ToggleSwitch";

export type Constraint = {
  id: string;
  name: string;
  query: string;
  enabled: boolean;
};

interface ConstraintEditorProps {
  enabled?: boolean;
  id?: string;
  onChange: (c: Constraint) => void;
  onDelete?: (c: Constraint) => void;
  name?: string;
  query?: string;
  readonly?: boolean;
}

export const ConstraintEditor = ({
  id,
  name,
  enabled = true,
  onChange,
  onDelete,
  query,
  readonly = true,
}: ConstraintEditorProps) => {
  const [isEnabled, setIsEnabled] = useState(enabled);
  const [newName, setNewName] = useState(name ?? "");
  const [newQuery, setNewQuery] = useState(query ?? "");

  const onUpdateName = useCallback(
    ({ target }: ChangeEvent<HTMLInputElement>) => setNewName(target.value),
    []
  );

  const onUpdateQuery = useCallback(
    ({ target }: ChangeEvent<HTMLInputElement>) => setNewQuery(target.value),
    []
  );

  const onDeleteQuery = useCallback(() => {
    if (onDelete && id && name && query) {
      onDelete({ id, name, query, enabled });
    }
  }, [enabled, id, name, onDelete, query]);

  return (
    <Form className="pt-2">
      <Form.Group controlId={`${name}-editor`}>
        {readonly ? (
          <Form.Label>{name}</Form.Label>
        ) : (
          <Form.Control
            className="mb-2"
            aria-placeholder="Enter a unique name for this set of constraints"
            value={newName}
            placeholder="Enter a unique name for this set of constraints"
            onChange={onUpdateName}
          />
        )}
        {readonly ? (
          <div className="bg-light p-3 rounded border">
            <pre className="mb-2">{query}</pre>
          </div>
        ) : (
          <Form.Control
            className="mb-2"
            as="textarea"
            rows={3}
            placeholder="Enter a valid query"
            value={newQuery}
            onChange={onUpdateQuery}
          />
        )}
        {!readonly && (
          <Row className="d-flex align-items-center">
            <Col xs="2">
              <ToggleSwitch
                checked={isEnabled}
                id={`${name}-enabled`}
                inline
                label={isEnabled ? "Enabled" : "Disabled"}
                onToggle={() => setIsEnabled((prev) => !prev)}
              />
            </Col>
            <Col xs="auto" className="d-flex justify-content-end flex-fill">
              <Button
                disabled={!(newName && newQuery)}
                onClick={() => {
                  if (newName && newQuery) {
                    if (id === undefined) {
                      setNewName("");
                      setNewQuery("");
                      setIsEnabled(true);
                    }

                    onChange({
                      id: id ?? uuidv4(),
                      name: newName,
                      query: newQuery,
                      enabled: isEnabled,
                    });
                  }
                }}
              >
                Save
              </Button>
              {onDelete && (
                <Button
                  style={{ marginLeft: "1em" }}
                  variant="secondary"
                  onClick={onDeleteQuery}
                >
                  Delete
                </Button>
              )}
            </Col>
          </Row>
        )}
      </Form.Group>
    </Form>
  );
};

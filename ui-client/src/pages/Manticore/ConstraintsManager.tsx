import { useCallback, useState } from "react";
import { Container, Tab, Tabs } from "react-bootstrap";
import { RiEdit2Fill, RiEdit2Line } from "react-icons/ri";

import { ConstraintEditor } from "./ConstraintEditor";
import type { Constraint } from "./ConstraintEditor";

const NEW_CONSTRAINT_TAB_KEY = "new-constraint";

interface ConstraintManagerProps {
  constraints: Constraint[];
  onAdd: (c: Constraint) => void;
  onDelete: (c: Constraint) => void;
  onUpdate: (c: Constraint) => void;
}

export const ConstraintsManager = ({
  constraints,
  onAdd,
  onDelete,
  onUpdate,
}: ConstraintManagerProps) => {
  const [activeTabKey, setActiveTabKey] = useState<string>(
    NEW_CONSTRAINT_TAB_KEY
  );
  const [currentEditTab, setCurrentEditTab] = useState<string | undefined>(
    undefined
  );

  const onAddConstraint = useCallback(
    (c: Constraint) => {
      setCurrentEditTab(undefined);
      setActiveTabKey(c.id.toString());
      onAdd(c);
    },
    [onAdd]
  );

  const onUpdateConstraint = useCallback(
    (c: Constraint) => {
      setCurrentEditTab(undefined);
      setActiveTabKey(c.id.toString());
      onUpdate(c);
    },
    [onUpdate]
  );

  const onDeleteConstraint = useCallback(
    (c: Constraint) => {
      setCurrentEditTab(undefined);
      setActiveTabKey(NEW_CONSTRAINT_TAB_KEY);
      onDelete(c);
    },
    [onDelete]
  );

  return (
    <Container className="py-2 border-bottom">
      <Tabs
        defaultActiveKey={NEW_CONSTRAINT_TAB_KEY}
        activeKey={activeTabKey}
        id="constraints-manager"
        onSelect={(eventKey) => {
          if (eventKey === "new-constraint") {
            setCurrentEditTab(undefined);
          } else if (
            currentEditTab !== undefined &&
            eventKey !== currentEditTab.toString()
          ) {
            setCurrentEditTab(undefined);
          }
          setActiveTabKey(eventKey ?? NEW_CONSTRAINT_TAB_KEY);
        }}
      >
        {constraints.map((c) => (
          <Tab
            key={c.id}
            eventKey={c.id}
            tabClassName={
              c.enabled ? "constraint-enabled" : "constraint-disabled"
            }
            title={
              <>
                {c.name}
                {currentEditTab === c.id ? (
                  <RiEdit2Fill onClick={() => setCurrentEditTab(undefined)} />
                ) : (
                  <RiEdit2Line onClick={() => setCurrentEditTab(c.id)} />
                )}
              </>
            }
          >
            <ConstraintEditor
              id={c.id}
              name={c.name}
              query={c.query}
              readonly={c.id !== currentEditTab}
              onChange={onUpdateConstraint}
              onDelete={onDeleteConstraint}
            />
          </Tab>
        ))}
        <Tab eventKey={NEW_CONSTRAINT_TAB_KEY} title="New Constraint">
          <ConstraintEditor readonly={false} onChange={onAddConstraint} />
        </Tab>
      </Tabs>
    </Container>
  );
};

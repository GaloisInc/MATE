import { useCallback, useState, ChangeEvent } from "react";
import { Alert, Button, Form, Modal } from "react-bootstrap";

interface SnapshotSaverProps {
  onSaveSnapshot: (label: string) => void;
}

export const SnapshotSaver = ({ onSaveSnapshot }: SnapshotSaverProps) => {
  const [showModal, setShowModal] = useState(false);
  const [snapshotLabel, setSnapshotLabel] = useState("");
  const [validationMessage, setValidationMessage] = useState("");

  const onToggleModal = useCallback(() => {
    setSnapshotLabel("");
    setValidationMessage("");
    setShowModal((prev) => !prev);
  }, []);
  const onSave = useCallback(() => {
    if (snapshotLabel) {
      setValidationMessage("");
      onSaveSnapshot(snapshotLabel);
      setSnapshotLabel("");
      setShowModal(false);
    } else {
      setValidationMessage("You must specify a label for this snapshot");
    }
  }, [onSaveSnapshot, snapshotLabel]);
  const onChangeLabel = useCallback(
    ({ target }: ChangeEvent<HTMLInputElement>) => {
      setSnapshotLabel(target.value);
    },
    []
  );

  return (
    <>
      <Button
        className="w-100 mb-2"
        size="sm"
        variant="primary"
        type="button"
        onClick={onToggleModal}
      >
        Save Snapshot
      </Button>
      <Modal show={showModal} onHide={onToggleModal}>
        <Modal.Header closeButton>
          <Modal.Title>Save Snapshot</Modal.Title>
        </Modal.Header>

        <Modal.Body>
          <p>
            Save a snapshot of your analysis for sharing and retrieving later
          </p>
          {validationMessage && (
            <Alert variant="danger">{validationMessage}</Alert>
          )}
          <Form>
            <Form.Group>
              <Form.Label>Snapshot Label</Form.Label>
              <Form.Control type="text" onChange={onChangeLabel}></Form.Control>
            </Form.Group>
          </Form>
        </Modal.Body>

        <Modal.Footer>
          <Button variant="secondary" onClick={onToggleModal}>
            Close
          </Button>
          <Button variant="primary" onClick={onSave}>
            Save
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
};

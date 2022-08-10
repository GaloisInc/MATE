import React from "react";
import { Modal } from "react-bootstrap";

import "../styles/LogViewer.scss";

interface LogViewerProps {
  logOwnerId?: string;
  logData?: string;
  onClose: () => void;
  show: boolean;
}

export const LogViewer: React.FC<LogViewerProps> = ({
  logData,
  logOwnerId,
  onClose,
  show,
}) => {
  return (
    <Modal className="LogViewer" show={show} onHide={() => onClose()} size="xl">
      <Modal.Header closeButton>
        Log for: {logOwnerId ?? "unknown"}
      </Modal.Header>
      <Modal.Body>
        <pre>
          <code>
            {logData
              ? logData.split(/\n/).map((l) => <span key={l}>{l}</span>)
              : "no log data available..."}
          </code>
        </pre>
      </Modal.Body>
    </Modal>
  );
};

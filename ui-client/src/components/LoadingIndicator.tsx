import React from "react";
import { Modal, Spinner } from "react-bootstrap";

import "../styles/LoadingIndicator.scss";

interface LoadingIndicatorParams {
  message?: string;
}

export const LoadingIndicator: React.FC<LoadingIndicatorParams> = ({
  message,
}) => {
  return (
    <Modal
      className="LoadingIndicator"
      show={true}
      size="sm"
      aria-labelledby="contained-modal-title-vcenter"
      centered
    >
      <Modal.Header>{message ?? "Loading..."}</Modal.Header>
      <Modal.Body>
        <Spinner animation="border" role="status" />
      </Modal.Body>
      <Modal.Footer></Modal.Footer>
    </Modal>
  );
};

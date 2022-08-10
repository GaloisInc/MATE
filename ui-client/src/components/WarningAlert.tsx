import React, { useState } from "react";

import { Alert } from "react-bootstrap";

interface WarningAlertProps {
  warning: string;
  customTitle?: string;
}

const DEFAULT_TITLE = "Warning:";

export const WarningAlert: React.FC<WarningAlertProps> = ({
  customTitle,
  warning,
}) => {
  const [show, setShow] = useState(true);
  const title = customTitle ?? DEFAULT_TITLE;
  return show && warning ? (
    <Alert
      className="WarningAlert m-0"
      variant="warning"
      onClose={() => setShow(false)}
      dismissible
    >
      <Alert.Heading>{title}</Alert.Heading>
      {warning}
    </Alert>
  ) : null;
};

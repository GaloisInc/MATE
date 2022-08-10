import React, { useState } from "react";

import { Alert } from "react-bootstrap";

interface IErrorAlertProps {
  errors: string[];
  customTitle?: string;
}

const DEFAULT_TITLE = "Encountered the following Errors:";

export const ErrorAlert: React.FC<IErrorAlertProps> = ({
  customTitle,
  errors,
}) => {
  const [show, setShow] = useState(true);
  const title = customTitle ?? DEFAULT_TITLE;
  return show && errors && errors.length > 0 ? (
    <Alert
      className="ErrorAlert m-0"
      variant="danger"
      onClose={() => setShow(false)}
      dismissible
    >
      <Alert.Heading>{title}</Alert.Heading>
      {
        <ul>
          {errors.map((e, i) => (
            <li key={`error-${e}`}>{e}</li>
          ))}{" "}
        </ul>
      }
    </Alert>
  ) : null;
};

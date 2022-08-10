import React from "react";
import { ReactNode } from "react";
import { Card } from "react-bootstrap";

import "../styles/Insight.scss";

interface InsightProps {
  children?: ReactNode;
}

export const Insight: React.FC<InsightProps> = ({ children }) => {
  return children ? (
    <Card className="Insight mt-2">
      <Card.Header>Insight</Card.Header>
      <Card.Body>
        <Card.Text>{children}</Card.Text>
      </Card.Body>
    </Card>
  ) : null;
};

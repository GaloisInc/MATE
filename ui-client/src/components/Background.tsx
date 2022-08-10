import React from "react";
import { Card } from "react-bootstrap";

import "../styles/Background.scss";

interface BackgroundProps {
  text?: string;
}

// WARNING: This code would be vulnerable to command injection if we allowed
// users to supply background text when registering analyses.
export const Background: React.FC<BackgroundProps> = ({ text }) => {
  return text ? (
    <Card className="Background mt-2">
      <Card.Header>Background</Card.Header>
      <Card.Body>
        <Card.Text dangerouslySetInnerHTML={{__html: text}}></Card.Text>
      </Card.Body>
    </Card>
  ) : null;
};

import { Card } from "react-bootstrap";

interface ChoicesProps {
  choices?: string[][];
  stateId: number;
}

export const Choices = ({ choices, stateId }: ChoicesProps) => {
  return (
    <div className="Choices">
      Mantiserve explored the following analysis forks:
      <div className="choices">
        {choices?.map((c, i) => (
          <Card className="choice mb-2" key={`${stateId}-choice-${i}`}>
            <Card.Body>
              For symbolic expression:
              <code className="ml-1">{c[0] ?? "N/A"}</code>
              Manticore assigned the value:
              <code className="ml-1">{c[1] ?? "N/A"}</code>
            </Card.Body>
          </Card>
        ))}
      </div>
    </div>
  );
};

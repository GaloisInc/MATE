import { useCallback, useState } from "react";
import { Accordion, Alert, Card } from "react-bootstrap";

import { Choices } from "./Choices";
import { Cases } from "./Cases";
import type { AnalysisResultCase } from "./Cases";

export type AnalysisResult = {
  cases: AnalysisResultCase[];
  children: AnalysisResult[];
  choices: string[][];
  state_id: number;
  error_msg?: string;
};

interface AnalysisResultsProps {
  isRoot?: boolean;
  results?: AnalysisResult[];
}

const resultHasBug = (result: AnalysisResult): boolean => {
  return (
    result.cases.length > 0 ||
    result.children.filter((c) => resultHasBug(c)).length > 0
  );
};

export const AnalysisResults = ({ isRoot, results }: AnalysisResultsProps) => {
  const [errorExpanded, setErrorExpanded] = useState(true);

  const onToggleErrorExpand = useCallback(
    () => setErrorExpanded((prev) => !prev),
    []
  );

  return results && results.length > 0 ? (
    <Accordion
      className={`p-0 m-0 ${isRoot && "shadow-sm"}`}
      defaultActiveKey={isRoot ? results[0].state_id.toString() : undefined}
    >
      {results.map((r) => (
        <Card key={r.state_id}>
          <Accordion.Toggle
            as={Card.Header}
            variant="link"
            eventKey={r.state_id.toString()}
          >
            {`State ${r.state_id}`}{" "}
            {resultHasBug(r) && <span>contains potential bug</span>}
          </Accordion.Toggle>
          <Accordion.Collapse eventKey={r.state_id.toString()}>
            <Card.Body style={{ paddingRight: "0.5em" }}>
              {r.error_msg && (
                <Alert variant="danger" className="error-message">
                  <span
                    onClick={onToggleErrorExpand}
                    className={`${
                      errorExpanded ? "expanded" : "collapse-ellipsis"
                    }`}
                  >
                    {r.error_msg}
                  </span>
                </Alert>
              )}
              <Choices choices={r.choices} stateId={r.state_id} />
              <Cases cases={r.cases} stateId={r.state_id} />
              {r.children.length > 0 && (
                <AnalysisResults results={r.children} />
              )}
            </Card.Body>
          </Accordion.Collapse>
        </Card>
      ))}
    </Accordion>
  ) : (
    <>No analysis results to display</>
  );
};

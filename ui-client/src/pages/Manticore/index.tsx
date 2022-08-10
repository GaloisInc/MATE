import { useParams } from "react-router";
import {
  Alert,
  Button,
  Col,
  Container,
  Form,
  Row,
  Spinner,
} from "react-bootstrap";

import { useManticore } from "../../hooks/useManticore";

import { AdvancedMenu } from "./AdvancedMenu";
import { AnalysisResults } from "./AnalysisResults";
import { ConstraintsManager } from "./ConstraintsManager";
import { FunctionSelector } from "../../components/FunctionSelector";
import { Page } from "../../components/Page";
import { PolicySelector } from "./PolicySelector";
import { Warnings } from "./Warnings";

import "../../styles/Manticore.scss";

interface FlowFinderUrlParams {
  buildId: string;
  poiId?: string;
}

export const Manticore = () => {
  const { buildId, poiId } = useParams<FlowFinderUrlParams>();

  const {
    // state
    taskId,
    analysisTaskRunning,
    binaryName,
    canRunAnalysis,
    constraints,
    error,
    functionNodes,
    memoryLimitMB,
    results,
    selectedFunction,
    taskError,
    timeLimitSeconds,
    warnings,
    // mutators
    onChangeMemoryLimit,
    onChangeObjectPolicy,
    onChangePrimitivesPolicy,
    onChangeTimeLimit,
    onDeleteConstraint,
    onSelectFunction,
    onAddConstraint,
    onUpdateConstraint,
    runAnalysis,
    stopAnalysis,
  } = useManticore({
    buildId,
    poiId,
  });

  return (
    <Page className="Manticore" buildId={buildId} binaryName={binaryName}>
      <Container fluid>
        {error && (
          <Alert className="my-2" variant="danger">
            {error}
          </Alert>
        )}
        {taskError && (
          <Alert className="my-2" variant="warning">
            {taskError}
          </Alert>
        )}
        <Row className="rounded border shadow-sm m-1 mt-3">
          <Form inline className="border-bottom">
            <Form.Row className="d-flex justify-content-between align-items-stretch">
              <Col xs={2}>
                <FunctionSelector
                  functionNodes={functionNodes}
                  label="Select a function"
                  onChange={onSelectFunction}
                  selectedId={selectedFunction?.id}
                />
              </Col>
              <Col xs={5} className="my-1">
                <PolicySelector
                  label="Select an object array size policy"
                  onChange={onChangeObjectPolicy}
                  tooltip="This policy controls Manticore's behavior on arrays containing non-primitive types, such as structures or objects. By default Manticore will choose reasonable lengths for arrays; users can override this and set custom lengths using the 'custom' policy."
                />
              </Col>
              <Col xs={4} className="my-1">
                <PolicySelector
                  label="Select a primitive array size policy"
                  onChange={onChangePrimitivesPolicy}
                  tooltip="This policy controls Manticore's behavior on arrays containing primitive types. By default Manticore will choose reasonable lengths for arrays; users can override this and set custom lengths using the 'custom' policy."
                />
              </Col>
              <Col xs={1} className="my-1">
                <Container className="mt-1">
                  <AdvancedMenu
                    memoryLimitMB={memoryLimitMB}
                    timeLimitSeconds={timeLimitSeconds}
                    onChangeMemoryLimit={onChangeMemoryLimit}
                    onChangeTimeLimit={onChangeTimeLimit}
                  />
                </Container>
              </Col>
            </Form.Row>
          </Form>
          <ConstraintsManager
            constraints={constraints}
            onAdd={onAddConstraint}
            onDelete={onDeleteConstraint}
            onUpdate={onUpdateConstraint}
          />
          <Container className="p-3 d-flex justify-content-end">
            {analysisTaskRunning? (
                <Button variant="warning" onClick={stopAnalysis} disabled={false}>
                  {<span>Stop Analysis</span>}
                </Button>
              ) : null }
            <Button onClick={runAnalysis} disabled={!canRunAnalysis}>
              {analysisTaskRunning ? (
                <Spinner
                  as="span"
                  animation="border"
                  size="sm"
                  role="status"
                  aria-hidden="true"
                />
              ) : null}
              {analysisTaskRunning ? (
                <span>Running: {taskId}</span>
              ) : <span>Run Analysis</span> }
            </Button>
          </Container>
        </Row>
        <Row className="pt-0 py-0 pb-4 m-1 results">
          <h5 className="mt-2">Analysis Results:</h5>
          <Warnings warnings={warnings} />
          <AnalysisResults isRoot={true} results={results} />
        </Row>
      </Container>
    </Page>
  );
};

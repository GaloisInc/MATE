import { useCallback, useState } from "react";
import type { ChangeEvent } from "react";
import { Col, Form, OverlayTrigger, Tooltip } from "react-bootstrap";
import { BiHelpCircle } from "react-icons/bi";

export type PolicyChoice = "default" | "custom";
type OptionalPolicyChoice = PolicyChoice | "none";

export interface Policy {
  policyChoice: PolicyChoice;
  customInputValues: number[];
}

const EMTPY_POLICY: OptionalPolicyChoice = "none";
const POLICY_CHOICES: PolicyChoice[] = ["default", "custom"];

const mapToPolicy = (maybePolicy: string): OptionalPolicyChoice => {
  switch (maybePolicy) {
    case "default":
      return "default";
    case "custom":
      return "custom";
    default:
      return "none";
  }
};

interface PolicySelectorProps {
  label: string;
  onChange: (p?: Policy) => void;
  tooltip: string;
}

export const PolicySelector = ({
  label,
  onChange,
  tooltip,
}: PolicySelectorProps) => {
  const [customInputValues, setCustomInputValues] = useState<number[]>([]);
  const [policyChoice, setPolicy] =
    useState<OptionalPolicyChoice>(EMTPY_POLICY);

  const onSelect = useCallback(
    (e: ChangeEvent<HTMLSelectElement>) => {
      const newPolicy = mapToPolicy(e.target.value);

      if (newPolicy === "none") {
        onChange(undefined);
      } else {
        onChange({
          policyChoice: newPolicy,
          customInputValues: [],
        });
      }

      setPolicy(newPolicy);

      if (newPolicy !== "custom") {
        setCustomInputValues([]);
      }
    },
    [onChange]
  );

  const onCustomInput = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      if (policyChoice !== EMTPY_POLICY) {
        const newCustomInputValues = e.target.value
          .split(/[^\d]+/g)
          .map<number>(Number);
        setCustomInputValues(newCustomInputValues);
        onChange({
          policyChoice: policyChoice,
          customInputValues: newCustomInputValues,
        });
      }
    },
    [onChange, policyChoice]
  );

  return (
    <Form.Row className="d-flex justify-content-around align-items-center PolicySelector">
      <Col xs={5}>
        <Form.Control as="select" onChange={onSelect} className="my-1 mx-sm-2">
          <option value={EMTPY_POLICY}>{label}</option>
          {POLICY_CHOICES.map((policyChoice) => (
            <option key={policyChoice} value={policyChoice}>
              Use {policyChoice}
            </option>
          ))}
        </Form.Control>
      </Col>
      <Col xs={6}>
        <Form.Control
          onChange={onCustomInput}
          className="my-1 mx-sm-2 last-control"
          placeholder="integers for 'custom' policy"
          value={customInputValues.map<string>((v) => v.toString())}
          disabled={policyChoice !== "custom"}
        />
        <OverlayTrigger
          placement="bottom"
          overlay={
            <Tooltip id="tooltip-object-array-size-policy">{tooltip}</Tooltip>
          }
        >
          <BiHelpCircle size="1em" className="help-icon" />
        </OverlayTrigger>
      </Col>
    </Form.Row>
  );
};

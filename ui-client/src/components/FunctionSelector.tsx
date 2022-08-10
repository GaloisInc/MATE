import { Typeahead } from "react-bootstrap-typeahead";

import { FlowFinderNode } from "../hooks/useFlowFinder";

interface FunctionSelectorProps {
  functionNodes?: FlowFinderNode[];
  label: string;
  onChange: (fns: FlowFinderNode[]) => void;
  selectedId?: string;
}

export const FunctionSelector = ({
  functionNodes = [],
  label,
  onChange,
  selectedId,
}: FunctionSelectorProps) => {
  return (
    <Typeahead<FlowFinderNode>
      id="fn-node-selector"
      className="mt-2"
      labelKey={(option: any) => option.data.label}
      options={functionNodes}
      onChange={onChange}
      placeholder={label}
      selected={functionNodes.filter((n) => n.id === selectedId)}
    />
  );
};

import { render, screen } from "@testing-library/react";

import { UiGraphSlice } from "../lib/api";
import { GraphCard } from "./GraphCard";

test("renders graph card", () => {
  const testGraph: UiGraphSlice = {
    nodes: [],
    edges: [],
    kind: "forward_dataflow",
    source: "TEST-SOURCE-ID",
    sink: "TEST-SINK-ID",
  };

  render(
    <GraphCard
      enabled={true}
      graphId="UNIQUE-ID"
      label="MY CARD HEADING"
      onClick={jest.fn()}
      onDelete={jest.fn()}
      onMouseEnter={jest.fn()}
      onMouseLeave={jest.fn()}
      onToggleEnabled={jest.fn()}
    >
      <GraphCard.SliceData
        analysisNodes={{}}
        graphId="TEST-ID"
        sliceData={testGraph}
        onAnalyze={jest.fn()}
        onDeleteNode={jest.fn()}
        onToggleAvoid={jest.fn()}
        onToggleFocus={jest.fn()}
      />
    </GraphCard>
  );
  const sourceText = screen.getByText(/Source:/);
  expect(sourceText).toBeInTheDocument();
});

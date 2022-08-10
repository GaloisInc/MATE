import React from "react";
import { render, screen } from "@testing-library/react";

import { Graph } from "./Graph";

test("renders a div wrapper for the graph", () => {
  render(
    <Graph
      graphs={[]}
      hiddenGraphIds={[]}
      hiddenNodeIds={new Set()}
      layoutConfig={{ name: "dagre" }}
    />
  );
  const element = screen.getByTestId("graph-wrapper");
  expect(element).toBeInTheDocument();
});

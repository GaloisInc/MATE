import { render, screen } from "@testing-library/react";

import { NodeTooltip } from "./NodeTooltip";

const EMPTY_NODE_KIND = "ArrayType";
const NONEMPTY_NODE_KIND = "Function";

describe("NodeTooltip", () => {
  test("renders nothing if no node passed in", () => {
    render(
      <NodeTooltip
        targetRef={jest.fn()}
        x={0}
        y={0}
        onAddNodeCard={jest.fn()}
        onSubmit={jest.fn()}
        onMouseleave={jest.fn()}
        onSetSink={jest.fn()}
        onSetSource={jest.fn()}
        show={true}
      />
    );
    const tooltipRootElem = screen.queryByTestId("tooltip");
    expect(tooltipRootElem).toBeNull();
  });

  test("renders nothing if the node is a kind that has no menu options", () => {
    render(
      <NodeTooltip
        targetRef={jest.fn()}
        x={0}
        y={0}
        node={{
          node_id: "FOO",
          node_kind: EMPTY_NODE_KIND,
          opcode: "",
          function_id: "",
          label: "",
          source_id: "",
        }}
        onAddNodeCard={jest.fn()}
        onSubmit={jest.fn()}
        onMouseleave={jest.fn()}
        onSetSink={jest.fn()}
        onSetSource={jest.fn()}
        show={true}
      />
    );
    const tooltipRootElem = screen.queryByTestId("tooltip");
    expect(tooltipRootElem).toBeNull();
  });

  test("renders nothing if pass a false 'show' flag", () => {
    render(
      <NodeTooltip
        targetRef={jest.fn()}
        x={0}
        y={0}
        node={{
          node_id: "FOO",
          node_kind: NONEMPTY_NODE_KIND,
          opcode: "",
          function_id: "",
          label: "",
          source_id: "",
        }}
        onAddNodeCard={jest.fn()}
        onSubmit={jest.fn()}
        onMouseleave={jest.fn()}
        onSetSink={jest.fn()}
        onSetSource={jest.fn()}
        show={false}
      />
    );
    const tooltipRootElem = screen.queryByTestId("tooltip");
    expect(tooltipRootElem).toBeNull();
  });

  test("renders menu if the node is a kind that has menu options", () => {
    render(
      <NodeTooltip
        targetRef={jest.fn()}
        x={0}
        y={0}
        node={{
          node_id: "FOO",
          node_kind: NONEMPTY_NODE_KIND,
          opcode: "",
          function_id: "",
          label: "",
          source_id: "",
        }}
        onAddNodeCard={jest.fn()}
        onSubmit={jest.fn()}
        onMouseleave={jest.fn()}
        onSetSink={jest.fn()}
        onSetSource={jest.fn()}
        show={true}
      />
    );
    const useAsDataflowText = screen.getByText("Show data flow from this node");
    expect(useAsDataflowText).toBeInTheDocument();
  });
});

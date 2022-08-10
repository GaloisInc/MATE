import { render, screen } from "@testing-library/react";

import { NodeSelector } from "./NodeSelector";

test("renders button to add node", () => {
  render(<NodeSelector onSelect={jest.fn()} />);
  const addNodeText = screen.getByText(/Add Node/i);
  expect(addNodeText).toBeInTheDocument();
});

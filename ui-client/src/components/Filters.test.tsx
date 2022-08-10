import { render, screen } from "@testing-library/react";

import { Filters } from "./Filters";

test("renders filters component", () => {
  render(<Filters initialChoices={[]} onSelect={jest.fn()} />);
  const filtersText = screen.getByText(/Hide Node/i);
  expect(filtersText).toBeInTheDocument();
});

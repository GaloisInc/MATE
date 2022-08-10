import { render, screen } from "@testing-library/react";

import { SliceSelector } from "./SliceSelector";

test("renders button to create new slice", () => {
  render(<SliceSelector onSelect={jest.fn()} />);
  const createSliceText = screen.getByText(/Create New Slice/i);
  expect(createSliceText).toBeInTheDocument();
});

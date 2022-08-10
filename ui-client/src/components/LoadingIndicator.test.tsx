import { render, screen } from "@testing-library/react";

import { LoadingIndicator } from "./LoadingIndicator";

test("renders simple 'loading' modal", () => {
  render(<LoadingIndicator />);
  const loadingText = screen.getByText(/Loading.../i);
  expect(loadingText).toBeInTheDocument();
});

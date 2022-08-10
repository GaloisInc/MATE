import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { Header } from "./Header";

test("renders application header", () => {
  render(<Header />, { wrapper: MemoryRouter });
  const headerText = screen.getByText(/MATE/i);
  expect(headerText).toBeInTheDocument();
});

import { MemoryRouter } from "react-router";
import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders header", () => {
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>
  );
  const linkElement = screen.getByText(/MATE/i);
  expect(linkElement).toBeInTheDocument();
});

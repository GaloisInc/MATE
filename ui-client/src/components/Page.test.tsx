import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { Page } from "./Page";

test("renders header content", () => {
  render(
    <Page>
      <div>TEST CONTENT</div>
    </Page>,
    { wrapper: MemoryRouter }
  );
  const headerText = screen.getByText(/MATE/i);
  expect(headerText).toBeInTheDocument();
});

test("renders child content", () => {
  render(
    <Page>
      <div>TEST CONTENT</div>
    </Page>,
    { wrapper: MemoryRouter }
  );
  const bodyText = screen.getByText(/TEST CONTENT/i);
  expect(bodyText).toBeInTheDocument();
});

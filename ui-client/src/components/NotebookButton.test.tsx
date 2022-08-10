import { render, screen } from "@testing-library/react";

import { NotebookButton } from "./NotebookButton";

describe("NotebookButton", () => {
  test("renders a button with label about creating a notebook", () => {
    render(
      <NotebookButton binaryName="TEST-BIN-NAME" buildId="TEST-BUILD-ID" />
    );
    const createLabelText = screen.getByText("Open Jupyter Notebook");
    expect(createLabelText).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";

import { Background } from "./Background";

describe("Background", () => {
  test("renders background information", () => {
    render(<Background text="TEST BACKGROUND" />);
    const bodyText = screen.getByText("TEST BACKGROUND");
    expect(bodyText).toBeInTheDocument();
  });

  test("renders nothing if no text given", () => {
    render(<Background text={undefined} />);
    const headingText = screen.queryByText("Background");
    expect(headingText).not.toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";

import { WarningAlert } from "./WarningAlert";

describe("WarningAlert", () => {
  it("should not render if no text passed in", async () => {
    render(<WarningAlert warning={""} />);
    expect(screen.queryByText(/Warning:/i)).not.toBeInTheDocument();
  });

  it("should render if warning passed in", () => {
    render(<WarningAlert warning={"TEST WARNING"} />);
    const warningText = screen.getByText(/TEST WARNING/i);
    expect(warningText).toBeInTheDocument();
  });
});

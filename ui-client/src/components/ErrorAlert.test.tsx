import { render, screen } from "@testing-library/react";

import { ErrorAlert } from "./ErrorAlert";

describe("ErrorAlert", () => {
  it("should not render if no errors passed in", async () => {
    render(<ErrorAlert errors={[]} />);
    expect(
      screen.queryByText(/Encountered the following Errors:/i)
    ).not.toBeInTheDocument();
  });

  it("should render if errors passed in", () => {
    render(<ErrorAlert errors={["TEST ERROR"]} />);
    const errorText = screen.getByText(/TEST ERROR/i);
    expect(errorText).toBeInTheDocument();
  });
});

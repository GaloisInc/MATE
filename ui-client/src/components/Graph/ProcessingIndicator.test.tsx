import { render, screen } from "@testing-library/react";

import { ProcessingIndicator } from "./ProcessingIndicator";

describe("ProcessingIndicator", () => {
  test("does not render if not processing", () => {
    render(<ProcessingIndicator isProcessing={false} />);
    const processingIcon = screen.queryByTitle("processing graph");
    expect(processingIcon).not.toBeInTheDocument();
  });
  test("renders simple 'hourglass' icon if processing", () => {
    render(<ProcessingIndicator isProcessing={true} />);
    const processingIcon = screen.getByTitle("processing graph");
    expect(processingIcon).toBeInTheDocument();
  });
});

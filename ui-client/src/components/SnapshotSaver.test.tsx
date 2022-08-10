import { render, screen } from "@testing-library/react";

import { SnapshotSaver } from "./SnapshotSaver";

describe("SnapshotSaver", () => {
  it("should render button", () => {
    render(<SnapshotSaver onSaveSnapshot={jest.fn()} />);
    const saveText = screen.getByText(/Save Snapshot/i);
    expect(saveText).toBeInTheDocument();
  });
});

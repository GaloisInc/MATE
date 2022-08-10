import { render, screen } from "@testing-library/react";

import { ToggleSwitch } from "./ToggleSwitch";

describe("ToggleSwitch", () => {
  test("allows for specifying a label", () => {
    render(<ToggleSwitch id="SOME-ID" onToggle={jest.fn()} label="MY LABEL" />);
    const switchLabel = screen.getByText(/MY LABEL/i);
    expect(switchLabel).toBeInTheDocument();
  });
  test("allows for rendering inline", () => {
    const { container } = render(
      <ToggleSwitch id="SOME-ID" onToggle={jest.fn()} label="MY LABEL" inline />
    );
    expect(container.getElementsByClassName("inline")).toHaveLength(1);
  });
  test("defaults to unchecked if no value passed in", () => {
    const { container } = render(
      <ToggleSwitch id="SOME-ID" onToggle={jest.fn()} label="MY LABEL" />
    );
    expect(
      container.getElementsByTagName("input").item(0)?.checked
    ).toBeFalsy();
  });
  test("allows to be defaulted to checked", () => {
    const { container } = render(
      <ToggleSwitch
        id="SOME-ID"
        onToggle={jest.fn()}
        label="MY LABEL"
        checked={true}
      />
    );
    expect(
      container.getElementsByTagName("input").item(0)?.checked
    ).toBeTruthy();
  });
});

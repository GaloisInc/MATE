import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { PanelGrid } from "./PanelGrid";

describe("PanelGrid", () => {
  describe("default behavior", () => {
    test("renders simple layout", () => {
      render(
        <PanelGrid
          onResize={jest.fn()}
          onDragStart={jest.fn()}
          onDragEnd={jest.fn()}
        >
          <PanelGrid.GraphWindow>MY GRAPH</PanelGrid.GraphWindow>
          <PanelGrid.CardWindow>MY CARDS</PanelGrid.CardWindow>
          <PanelGrid.RightSidebar>MY SIDEBAR</PanelGrid.RightSidebar>
        </PanelGrid>,
        { wrapper: MemoryRouter }
      );
      const graphText = screen.getByText(/MY GRAPH/i);
      expect(graphText).toBeInTheDocument();
      const cardText = screen.getByText(/MY CARDS/i);
      expect(cardText).toBeInTheDocument();
      const sidebarText = screen.getByText(/MY SIDEBAR/i);
      expect(sidebarText).toBeInTheDocument();
    });
  });
});

import { render, screen } from "@testing-library/react";

import { Paginator } from "./Paginator";

describe("Paginator", () => {
  describe("when no pages", () => {
    test('it should tell the user we have "0 of 0" pages', () => {
      render(
        <Paginator
          pageCount={0}
          pageIndex={0}
          pageSize={10}
          pageSizeChoices={[10, 1000000]}
          canPreviousPage={false}
          canNextPage={false}
          handlePreviousPage={jest.fn()}
          handleFirstPage={jest.fn()}
          handleLastPage={jest.fn()}
          handleNextPage={jest.fn()}
          setPageSize={jest.fn()}
        />
      );
      expect(screen.queryByText(/0 of 0/i)).not.toBeNull();
    });
  });
});

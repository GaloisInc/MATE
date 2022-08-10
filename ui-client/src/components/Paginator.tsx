import { Form, Pagination } from "react-bootstrap";

import "../styles/Paginator.scss";

interface PaginatorProps {
  canNextPage: boolean;
  canPreviousPage: boolean;
  handleFirstPage: () => void;
  handleLastPage: () => void;
  handleNextPage: () => void;
  handlePreviousPage: () => void;
  pageCount: number;
  pageIndex: number;
  pageSize: number;
  pageSizeChoices: number[];
  setPageSize: (newSize: number) => void;
}

export const Paginator = ({
  canNextPage,
  canPreviousPage,
  handleFirstPage,
  handleLastPage,
  handleNextPage,
  handlePreviousPage,
  pageCount,
  pageIndex,
  pageSize,
  pageSizeChoices,
  setPageSize,
}: PaginatorProps) => {
  const currPage = pageCount > 0 ? pageIndex + 1 : 0;

  return (
    <div className="Paginator">
      <Pagination>
        <Pagination.First onClick={handleFirstPage} />
        <Pagination.Prev
          disabled={!canPreviousPage}
          onClick={handlePreviousPage}
        />
        <Pagination.Item className="page-size">
          <Form.Control
            as="select"
            size="sm"
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
            }}
          >
            {pageSizeChoices.map((sizeOption) => (
              <option key={sizeOption} value={sizeOption}>
                Show {sizeOption}
              </option>
            ))}
          </Form.Control>
        </Pagination.Item>
        <Pagination.Next disabled={!canNextPage} onClick={handleNextPage} />
        <Pagination.Last onClick={handleLastPage} />
        <span className="page-place font-weight-ligther">
          Page{" "}
          <em>
            {currPage} of {pageCount}
          </em>
        </span>
      </Pagination>
    </div>
  );
};

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Container } from "react-bootstrap";
import { usePagination, useTable, useSortBy, Column, Row } from "react-table";
import {
  TiArrowSortedDown,
  TiArrowSortedUp,
  TiArrowUnsorted,
} from "react-icons/ti";

import { Page } from "../components/Page";
import { Paginator } from "../components/Paginator";
import { ErrorAlert } from "../components/ErrorAlert";
import { LogViewer } from "../components/LogViewer";
import { ToggleSwitch } from "../components/ToggleSwitch";
import { getCompilationLog } from "../lib/api";
import type { BuildCompilation, CompilationSourceArtifact } from "../lib/api";
import { useCompilations } from "../hooks/api/useCompilations";

import "../styles/Compilations.scss";

export const Compilations: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentCompilation, setCurrentCompilation] = useState<
    BuildCompilation | undefined
  >(undefined);
  const [currentLogData, setCurrentLogData] = useState<string | undefined>(
    undefined
  );
  const [showLog, setShowLog] = useState(false);
  const [shouldHideFailedCompilations, setShouldHideFailedCompilations] =
    useState(false);

  const { compilations } = useCompilations({});

  useEffect(() => {
    setError(null);
    setIsLoading(true);
  }, []);

  useEffect(() => {
    if (compilations) {
      setIsLoading(false);
    }
  }, [compilations]);

  useEffect(() => {
    if (currentCompilation?.logArtifact?.id) {
      setError(null);
      setIsLoading(true);
      setCurrentLogData(undefined);
      getCompilationLog(currentCompilation.logArtifact.id)
        .then((logData) => setCurrentLogData(logData))
        .catch((e: any) => {
          setError(e.message);
          console.error(e);
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [currentCompilation]);

  const toggleHidingOfFailedCompilations = useCallback(() => {
    setShouldHideFailedCompilations((prev) => !prev);
  }, []);

  const caseInsensitiveCmp = (a: Row, b: Row, columnId: string) => {
    try {
      switch (columnId) {
        case "Name":
          return a.values[columnId].attributes.challenge_name.localeCompare(
            b.values[columnId].attributes.challenge_name
          );
        case "Target":
          return a.values[columnId].attributes.target_id.localeCompare(
            b.values[columnId].attributes.target_id
          );
        case "id":
          return a.values[columnId].localeCompare(b.values[columnId]);
        default:
          throw new Error(`Unknown attribute (${columnId})`);
      }
    } catch (e) {
      console.error(e);
      return 1; // HACK: because TypeScript cannot help us here (values are just Record<string, any>)
    }
  };

  // NOTE: "accessor" needs to be cast as a const to work
  // https://github.com/tannerlinsley/react-table/discussions/2664
  const columns = useMemo(
    () =>
      [
        {
          Header: "Compilation Id",
          accessor: "id" as const, // accessor is the "key" in the data
          sortType: caseInsensitiveCmp,
        },
        {
          Header: "Target",
          accessor: (
            compilation: BuildCompilation
          ): CompilationSourceArtifact => compilation.sourceArtifact,
          Cell: ({ value }: any) => {
            if (value.kind === "compile-target:brokered-challenge") {
              return value.attributes.target_id;
            } else {
              return "N/A";
            }
          },
          sortType: caseInsensitiveCmp,
        },
        {
          Header: "Name",
          accessor: (
            compilation: BuildCompilation
          ): CompilationSourceArtifact => compilation.sourceArtifact,
          Cell: ({ value }: any) => {
            if (value.kind === "compile-target:brokered-challenge") {
              return value.attributes.challenge_name;
            } else {
              return "N/A";
            }
          },
          sortType: caseInsensitiveCmp,
        },
        {
          Header: "Filename",
          accessor: (
            compilation: BuildCompilation
          ): CompilationSourceArtifact => compilation.sourceArtifact,
          Cell: ({ value }: any) => value.attributes.filename,
          sortType: caseInsensitiveCmp,
        },
        {
          Header: "State",
          accessor: "state" as const,
          sortType: "alphanumeric",
        },
        {
          Header: "Log",
          accessor: (
            compilation: BuildCompilation
          ): BuildCompilation | undefined => compilation,
          Cell: ({ row: { index }, value }: any) => {
            return value ? (
              <span
                onClick={() => {
                  setCurrentCompilation(value);
                  setShowLog(true);
                }}
              >
                view log
              </span>
            ) : (
              "N/A"
            );
          },
        },
      ] as Column[],
    []
  );
  const data = useMemo(
    () =>
      compilations
        ? shouldHideFailedCompilations
          ? compilations.filter((c: BuildCompilation) => c.state !== "failed")
          : compilations
        : [],
    [compilations, shouldHideFailedCompilations]
  );

  const {
    canNextPage,
    canPreviousPage,
    getTableProps,
    getTableBodyProps,
    gotoPage,
    headerGroups,
    nextPage,
    page,
    pageCount,
    prepareRow,
    previousPage,
    setPageSize,
    state: { pageIndex, pageSize },
  } = useTable(
    { columns, data, initialState: { pageSize: 10 } },
    useSortBy,
    usePagination
  );

  const handleFirstPage = useCallback(() => gotoPage(0), [gotoPage]);
  const handlePreviousPage = useCallback(() => previousPage(), [previousPage]);
  const handleNextPage = useCallback(() => nextPage(), [nextPage]);
  const handleLastPage = useCallback(
    () => gotoPage(pageCount - 1),
    [gotoPage, pageCount]
  );

  return (
    <Page isLoading={isLoading}>
      <Container className="Compilations m5 h-100" fluid>
        {error && <ErrorAlert errors={[error]} />}
        <LogViewer
          logOwnerId={currentCompilation?.sourceArtifact.id}
          logData={currentLogData}
          show={showLog && !isLoading}
          onClose={() => setShowLog(false)}
        />
        <div className="filters">
          <ToggleSwitch
            id="toggle-failed-compilations"
            inline
            label="Hide Failed Compilations"
            onToggle={toggleHidingOfFailedCompilations}
            checked={shouldHideFailedCompilations}
          />
          <Paginator
            canNextPage={canNextPage}
            canPreviousPage={canPreviousPage}
            handleFirstPage={handleFirstPage}
            handleLastPage={handleLastPage}
            handleNextPage={handleNextPage}
            handlePreviousPage={handlePreviousPage}
            pageCount={pageCount}
            pageIndex={pageIndex}
            pageSize={pageSize}
            pageSizeChoices={[10, 25, 50, 100]}
            setPageSize={setPageSize}
          />
        </div>
        <table {...getTableProps()} className="table table-hover">
          <thead>
            {headerGroups.map((headerGroup) => (
              <tr {...headerGroup.getHeaderGroupProps()}>
                {headerGroup.headers.map((column) => (
                  <th {...column.getHeaderProps(column.getSortByToggleProps())}>
                    {column.render("Header")}
                    <span>
                      {column.canSort &&
                        (column.isSorted ? (
                          column.isSortedDesc ? (
                            <TiArrowSortedDown />
                          ) : (
                            <TiArrowSortedUp />
                          )
                        ) : (
                          <TiArrowUnsorted />
                        ))}
                    </span>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody {...getTableBodyProps()}>
            {page.map((row, i) => {
              prepareRow(row);
              return (
                <tr {...row.getRowProps()}>
                  {row.cells.map((cell) => {
                    return (
                      <td {...cell.getCellProps()}>{cell.render("Cell")}</td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </Container>
    </Page>
  );
};

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Container, Spinner } from "react-bootstrap";
import {
  usePagination,
  useSortBy,
  useTable,
  Cell,
  Column,
  Row,
  SortByFn,
} from "react-table";
import { Link } from "react-router-dom";
import {
  TiArrowSortedDown,
  TiArrowSortedUp,
  TiArrowUnsorted,
} from "react-icons/ti";

import { usePage } from "../hooks/usePage";
import { useBuilds } from "../hooks/api/useBuilds";
import { Page } from "../components/Page";
import { ErrorAlert } from "../components/ErrorAlert";
import { NotebookButton } from "../components/NotebookButton";
import { Paginator } from "../components/Paginator";
import { ToggleSwitch } from "../components/ToggleSwitch";
import type { Build, CompilationSourceArtifact } from "../lib/api";

import "../styles/Builds.scss";

const caseInsensitiveCmp: SortByFn<Build> = (
  a: Row<Build>,
  b: Row<Build>,
  columnId: string
) => {
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

const buildStateCmp: SortByFn<Build> = (
  a: Row<Build>,
  b: Row<Build>,
  columnId: string
) => {
  const buildStateOrder = [
    "built",
    "inserting",
    "building",
    "created",
    "failed",
  ];

  return (
    buildStateOrder.indexOf(a.values[columnId]) -
    buildStateOrder.indexOf(b.values[columnId])
  );
};

const isBuildDone = (build: Build) =>
  build.state === "built" || build.state === "failed";

export const Builds: React.FC = () => {
  const { isLoading, loadingMessage, setIsLoading, setLoadingMessage } =
    usePage();
  const [error, setError] = useState<string | null>(null);
  const [shouldHideFailedBuilds, setShouldHideFailedBuilds] = useState(false);

  const { builds, isLoadingBuilds, isLoadingRebuild, rebuildBuild } = useBuilds(
    {}
  );

  useEffect(() => {
    setError(null);
    setIsLoading(true);
    setLoadingMessage("Fetching builds...");
  }, [setIsLoading, setLoadingMessage]);

  useEffect(() => {
    if (!(isLoadingBuilds && isLoadingRebuild)) {
      setIsLoading(false);
    }
  }, [isLoadingBuilds, isLoadingRebuild, setIsLoading]);

  const handleRebuild = useCallback(
    (compilationId: string, binaryFilename: string, buildId: string) => {
      setIsLoading(true);
      setLoadingMessage(`Requesting rebuild...`);
      rebuildBuild({ compilationId, binaryFilename, buildId });
    },
    [rebuildBuild, setIsLoading, setLoadingMessage]
  );

  // NOTE: "accessor" needs to be cast as a const to work
  // https://github.com/tannerlinsley/react-table/discussions/2664
  const columns = useMemo<Column<Build>[]>(
    () => [
      {
        Header: "POIs",
        accessor: (build: Build): { id: string; state: string } => {
          return {
            id: build.id,
            state: build.state,
          };
        },
        Cell: ({ value: { id, state } }: any) => {
          if (state === "built") {
            return <Link to={`/pois/${id}`}>view POIs</Link>;
          } else {
            return "N/A";
          }
        },
        disableSortBy: true,
      },
      {
        Header: "Code Graph",
        accessor: (build: Build): { id: string; state: string } => ({
          id: build.id,
          state: build.state,
        }),
        Cell: ({ value: { id, state } }: any) => {
          if (state === "built") {
            return <Link to={`/flow-finder/${id}`}>analyze in Flowfinder</Link>;
          } else {
            return "N/A";
          }
        },
        disableSortBy: true,
      },
      {
        Header: "Manticore",
        accessor: (build: Build): { id: string; state: string } => ({
          id: build.id,
          state: build.state,
        }),
        Cell: ({ value: { id, state } }: any) => {
          if (state === "built") {
            return <Link to={`/manticore/${id}`}>analyze in Manticore</Link>;
          } else {
            return "N/A";
          }
        },
        disableSortBy: true,
      },
      {
        Header: "Build Id",
        accessor: "id" as const, // accessor is the "key" in the data
        sortType: caseInsensitiveCmp,
      },
      {
        Header: "Target",
        accessor: (build: Build): CompilationSourceArtifact =>
          build.compilation.sourceArtifact,
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
        accessor: (build: Build): CompilationSourceArtifact =>
          build.compilation.sourceArtifact,
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
        Header: "Binary",
        accessor: (build: Build): string =>
          build.bitcodeArtifact.attributes.binary_filename as string,
        sortType: "alphanumeric",
      },
      {
        Header: "Merged Libraries",
        accessor: (build: Build): string => {
          if (build.mergeLibraryBitcode) {
            return "true";
          } else {
            return "false";
          }
        },
      },
      {
        Header: "Context Sensitivity",
        accessor: (build: Build): string => {
          if (build.options.do_pointer_analysis) {
            return build.contextSensitivity as string;
          } else {
            return "N/A (Pointer Analysis disabled)";
          }
        },
        sortType: "alphanumeric",
      },
      {
        Header: "State",
        accessor: "state" as const,
        sortType: buildStateCmp,
        Cell: ({ row: { original } }: Cell<Build>) => {
          const { state } = original;

          return (
            <>
              {state} {!isBuildDone(original) && <Spinner animation="border" />}
            </>
          );
        },
      },
      {
        Header: "Troubleshooting",
        accessor: (
          build: Build
        ): {
          compilation_id: string;
          state: string;
          binary_filename: string;
          id: string;
          rebuiltBy: string;
        } => {
          return {
            id: build.id,
            compilation_id: build.compilation.id,
            state: build.state,
            rebuiltBy: build.attributes.rebuiltBy
              ? (build.attributes.rebuiltBy as string)
              : "",
            binary_filename: build.bitcodeArtifact.attributes
              .binary_filename as string,
          };
        },
        Cell: ({
          value: { binary_filename, compilation_id, id, rebuiltBy, state },
        }: Cell<Build>) => {
          if (state === "failed" && !rebuiltBy) {
            return (
              <Button
                size="sm"
                variant="light"
                onClick={() =>
                  handleRebuild(compilation_id, binary_filename, id)
                }
              >
                Rebuild with Minimal Settings
              </Button>
            );
          } else {
            return "N/A";
          }
        },
        disableSortBy: true,
      },
      {
        Header: "Notebook",
        accessor: (build: Build): { id: string; binaryName: string } => {
          return {
            id: build.id,
            binaryName: build.bitcodeArtifact.attributes
              .binary_filename as string,
          };
        },
        Cell: ({ value: { binaryName, id } }: Cell<Build>) => {
          return (
            <NotebookButton buildId={id} binaryName={binaryName} size="sm" />
          );
        },
      },
    ],
    [handleRebuild]
  );
  const data = useMemo<Build[]>(() => {
    if (builds) {
      return shouldHideFailedBuilds
        ? builds.filter((b: Build) => b.state !== "failed")
        : builds;
    } else {
      return [];
    }
  }, [builds, shouldHideFailedBuilds]);

  const toggleHidingOfFailedBuilds = useCallback(() => {
    setShouldHideFailedBuilds((prev) => !prev);
  }, []);

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
    <Page isLoading={isLoading} loadingMessage={loadingMessage}>
      <Container className="Builds m5 h-100" fluid>
        {error && <ErrorAlert errors={[error]} />}
        <div className="filters">
          <ToggleSwitch
            id="toggle-failed-builds"
            inline
            label="Hide Failed Builds"
            onToggle={toggleHidingOfFailedBuilds}
            checked={shouldHideFailedBuilds}
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
        <table {...getTableProps()} className="table table-hover build-results">
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

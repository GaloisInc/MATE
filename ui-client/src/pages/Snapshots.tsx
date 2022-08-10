import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Container } from "react-bootstrap";
import {
  TiArrowSortedDown,
  TiArrowSortedUp,
  TiArrowUnsorted,
} from "react-icons/ti";
import { AiFillFolderOpen } from "react-icons/ai";
import { usePagination, useTable, useSortBy } from "react-table";
import type { Cell, Column } from "react-table";

import { usePage } from "../hooks/usePage";
import { useBuild } from "../hooks/api/useBuild";
import { useSnapshots } from "../hooks/api/useSnapshots";
import { Page } from "../components/Page";
import { Paginator } from "../components/Paginator";
import { ErrorAlert } from "../components/ErrorAlert";
import type { FlowFinderSnapshot } from "../lib/api";

import "../styles/Snapshots.scss";

type BinaryName = Record<string, string>;

export const Snapshots = () => {
  const { isLoading, loadingMessage, setIsLoading, setLoadingMessage } =
    usePage();
  const [error, setError] = useState<string | null>(null);
  const [binaryNames, setBinaryNames] = useState<BinaryName>({});
  const [buildIds, setBuildIds] = useState<string[]>([]);

  const { builds } = useBuild({ buildIds });
  const { snapshots } = useSnapshots({});

  // Fetch initial snapshot data
  useEffect(() => {
    setError(null);
    setIsLoading(true);
    setLoadingMessage("Fetching snapshots...");
  }, [setIsLoading, setLoadingMessage]);

  useEffect(() => {
    if (snapshots) {
      setIsLoading(false);
      setBuildIds(snapshots.map((s) => s.build_id));
    }
  }, [setIsLoading, snapshots]);

  // Fetch binary names for each build mentioned in each snapshot
  useEffect(() => {
    if (snapshots && snapshots.length > 0 && builds.length > 0) {
      const snapshotByBuildId = snapshots.reduce<
        Record<string, FlowFinderSnapshot>
      >((acc, s) => {
        return {
          ...acc,
          [s.build_id]: s,
        };
      }, {});

      const binaryFilenames = builds.reduce<BinaryName>((acc, b) => {
        const snap = snapshotByBuildId[b.id];
        if (snap !== undefined) {
          acc[snap.id] = b.bitcodeArtifact.attributes.binary_filename as string;
        }
        return acc;
      }, {});

      setBinaryNames(binaryFilenames);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [builds.length, snapshots]);

  // NOTE: "accessor" needs to be cast as a const to work
  // https://github.com/tannerlinsley/react-table/discussions/2664
  const columns = useMemo<Column<FlowFinderSnapshot>[]>(
    () => [
      {
        Header: " ",
        accessor: (
          snapshot: FlowFinderSnapshot
        ): { id: string; buildId: string; poiId?: string } => ({
          id: snapshot.id,
          buildId: snapshot.build_id,
          poiId: snapshot.poi_result_id,
        }),
        disableSortBy: true,
        Cell: ({ value: { id, buildId, poiId } }: Cell<FlowFinderSnapshot>) => (
          <Link
            to={`/flow-finder/${buildId}/snapshot/${id}${
              poiId ? `/${poiId}` : ""
            }`}
          >
            <AiFillFolderOpen />
          </Link>
        ),
      },
      {
        Header: "Label",
        accessor: "label" as const, // accessor is the "key" in the data
      },
      {
        Header: "Build Id",
        accessor: "build_id" as const,
      },
      {
        Header: "Binary",
        accessor: (snapshot: FlowFinderSnapshot): string => {
          return binaryNames[snapshot.id];
        },
      },
      {
        Header: "Originating POI",
        accessor: (snapshot: FlowFinderSnapshot): string => {
          if (snapshot.poi_result_id !== null) {
            return snapshot.poi_result_id as string;
          } else {
            return "N/A";
          }
        },
      },
    ],
    [binaryNames]
  );

  const data = useMemo<FlowFinderSnapshot[]>(
    () => snapshots ?? [],
    [snapshots]
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
    <Page isLoading={isLoading} loadingMessage={loadingMessage}>
      <Container className="Snapshots m5 h-100" fluid>
        {error && <ErrorAlert errors={[error]} />}
        <div className="filters">
          <div className="spacer"></div>
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

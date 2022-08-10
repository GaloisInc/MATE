import React, { useCallback, useEffect, useMemo, useState } from "react";
import { marked } from "marked";
import type { ChangeEvent } from "react";
import { Alert, Container, Form, Spinner } from "react-bootstrap";
import { useParams, Link } from "react-router-dom";
import { usePagination, useTable, useSortBy } from "react-table";
import type { Cell, Column } from "react-table";
import {
  TiArrowSortedDown,
  TiArrowSortedUp,
  TiArrowUnsorted,
} from "react-icons/ti";

import { Page } from "../components/Page";
import { Paginator } from "../components/Paginator";
import { ErrorAlert } from "../components/ErrorAlert";
import { ToggleSwitch } from "../components/ToggleSwitch";
import { NotebookButton } from "../components/NotebookButton";
import type { AnalysisTask, Build, POI } from "../lib/api";
import { usePage } from "../hooks/usePage";
import { useBuild } from "../hooks/api/useBuild";
import { usePOIs } from "../hooks/api/usePois";
import { useAnalysisTasks } from "../hooks/api/useAnalysisTasks";

import "../styles/POIs.scss";

const reduceAnalysisNames = (pois: POI[]) =>
  Array.from(
    pois.reduce((names, p) => {
      names.add(p.analysis_name);
      return names;
    }, new Set<string>())
  );

const isTaskDone = (task: AnalysisTask) =>
  task.state === "completed" || task.state === "failed";

const BuildInfo: React.FC<{ build: Build }> = ({ build }) => {
  return (
    <Alert variant="dark">
      <h4>Build: {build.id}</h4>
      <h5>
        Target:{" "}
        {build.compilation.sourceArtifact.kind ===
        "compile-target:brokered-challenge"
          ? build.compilation.sourceArtifact.attributes.target_id
          : "N/A"}
      </h5>
      <h5>
        Name:{" "}
        {build.compilation.sourceArtifact.kind ===
        "compile-target:brokered-challenge"
          ? build.compilation.sourceArtifact.attributes.challenge_name
          : "N/A"}
      </h5>
      <h5>Binary: {build.bitcodeArtifact.attributes.binary_filename}</h5>
      <h5>State: {build.state}</h5>
      <h5>Options: {JSON.stringify(build.options, null, 2)}</h5>
    </Alert>
  );
};

const AnalysisTasks: React.FC<{ analysisTasks: AnalysisTask[] }> = ({
  analysisTasks,
}) => {
  const data = useMemo(() => analysisTasks, [analysisTasks]);

  // NOTE: "accessor" needs to be cast as a const to work
  // https://github.com/tannerlinsley/react-table/discussions/2664
  const columns = useMemo<Column<AnalysisTask>[]>(
    () => [
      {
        id: "analysisName",
        Header: "Analysis Name",
        accessor: "analysis_name" as const,
        sortType: "basic",
      },
      {
        Header: "State",
        accessor: "state" as const,
        sortType: "basic",
        Cell: ({ row: { original } }: Cell<AnalysisTask>) => {
          const { state } = original;

          return (
            <>
              {state} {!isTaskDone(original) && <Spinner animation="border" />}
            </>
          );
        },
      },
      {
        Header: "POIs Generated",
        sortType: "basic",
        Cell: ({ row: { original } }: Cell<AnalysisTask>) => {
          const { poi_result_ids } = original;

          return isTaskDone(original) ? poi_result_ids.length : "-";
        },
      },
    ],
    []
  );

  const { getTableProps, getTableBodyProps, headerGroups, rows, prepareRow } =
    useTable(
      {
        columns,
        data,
        initialState: { sortBy: [{ id: "analysisName", desc: false }] },
        autoResetSortBy: false,
        autoResetRowState: false,
      },
      useSortBy
    );

  return (
    <table {...getTableProps()} className="table table-hover analysisTasks">
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
        {rows.map((row, i) => {
          prepareRow(row);
          return (
            <tr {...row.getRowProps()}>
              {row.cells.map((cell) => {
                return <td {...cell.getCellProps()}>{cell.render("Cell")}</td>;
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};

const PAGINATION_SIZE_CHOICES = [10, 25, 50, 100];
const DEFAULT_PAGINATION_CHOICE = 0; // index into PAGINATION_SIZE_CHOICES

export const PointsOfInterest: React.FC = () => {
  const { isLoading, loadingMessage, setIsLoading, setLoadingMessage } =
    usePage();

  const [error, setError] = useState<string | null>(null);
  const [analysisNames, setAnalysisNames] = useState<string[]>([]);
  const [analysisFilter, setAnalysisFilter] = useState("");
  const [flagged, setFlagged] = useState<{
    id: string;
    value: boolean;
  } | null>(null);
  const [todo, setTodo] = useState<{
    id: string;
    value: boolean;
  } | null>(null);
  const [shouldHideFlaggedPOIs, setShouldHideFlaggedPOIs] = useState(false);
  const [shouldHideDonePOIs, setShouldHideDonePOIs] = useState(false);
  useState(false);
  const [binaryName, setBinaryName] = useState<string | undefined>(undefined);

  const { buildId } = useParams<{ buildId: string }>();
  const { builds, isLoadingBuilds } = useBuild({
    buildIds: [buildId],
  });
  const {
    pois,
    poiErrors,
    isLoadingPOI,
    refetchPOIs,
    togglePOIIsDone,
    togglePOIIsFlagged,
  } = usePOIs({ buildId });
  const { analysisTasks, isLoadingAnalysisTasks } = useAnalysisTasks({
    buildId,
  });

  const processPOIs = (pois: POI[]): POI[] => {
    setAnalysisNames(reduceAnalysisNames(pois));
    return pois;
  };

  // Initial data fetch
  useEffect(() => {
    setError(null);
    setIsLoading(true);
    setLoadingMessage("Fetching initial page data...");
  }, [setIsLoading, setLoadingMessage]);

  // get binary name from our build
  useEffect(() => {
    if (builds[0]) {
      setBinaryName(
        builds[0].bitcodeArtifact.attributes.binary_filename as string
      );
    }
  }, [builds]);

  // do final processing on POIs when then load
  useEffect(() => {
    if (pois && pois.length > 0) {
      processPOIs(pois);
    }
  }, [pois]);

  // Indicate loading is finished
  useEffect(() => {
    setIsLoading(isLoadingAnalysisTasks || isLoadingPOI || isLoadingBuilds);
  }, [isLoadingAnalysisTasks, isLoadingPOI, isLoadingBuilds, setIsLoading]);

  useEffect(() => {
    if (poiErrors.length > 0) {
      console.error(poiErrors);
      setError(poiErrors.map((e) => e.message).join(", "));
    }
  }, [poiErrors]);

  // Update todo status
  useEffect(() => {
    if (todo !== null) {
      setError(null);
      setIsLoading(true);
      setLoadingMessage("Saving todo status...");
      togglePOIIsDone({ poiId: todo.id, isDone: todo.value });
    }
  }, [
    buildId,
    refetchPOIs,
    setIsLoading,
    setLoadingMessage,
    todo,
    togglePOIIsDone,
  ]);

  // Update flagged status
  useEffect(() => {
    if (flagged !== null) {
      setError(null);
      setIsLoading(true);
      setLoadingMessage("Saving flag status...");
      togglePOIIsFlagged({ poiId: flagged.id, isFlagged: flagged.value });
    }
  }, [
    buildId,
    flagged,
    refetchPOIs,
    setIsLoading,
    setLoadingMessage,
    togglePOIIsFlagged,
  ]);

  const toggleHidingOfFlaggedPOIs = useCallback(() => {
    setShouldHideFlaggedPOIs((prev) => !prev);
  }, []);

  const toggleHidingOfDonePOIs = useCallback(() => {
    setShouldHideDonePOIs((prev) => !prev);
  }, []);

  const data = useMemo<POI[]>(() => {
    return (
      pois
        ?.filter((p) => (shouldHideFlaggedPOIs ? !p.flagged : true))
        .filter((p) => (shouldHideDonePOIs ? !p.done : true))
        .filter((p) =>
          analysisFilter ? p.analysis_name === analysisFilter : true
        ) ?? []
    );
  }, [analysisFilter, pois, shouldHideDonePOIs, shouldHideFlaggedPOIs]);

  // NOTE: "accessor" needs to be cast as a const to work
  // https://github.com/tannerlinsley/react-table/discussions/2664
  const columns = useMemo<Column<POI>[]>(
    () => [
      {
        Header: "Code Graph",
        accessor: "build_id" as const, // accessor is the "key" in the data
        sortable: false,
        Cell: ({ row: { index }, value }: Cell<POI>) => {
          if (data.length > 0) {
            const { poi_result_id } = data[index];
            return (
              <Link to={`/flow-finder/${value}/poi/${poi_result_id}`}>
                analyze
              </Link>
            );
          } else {
            return "...";
          }
        },
        disableSortBy: true,
      },
      {
        Header: "Flagged",
        accessor: "flagged" as const,
        sortType: "basic",
        Cell: ({ row: { original } }: Cell<POI>) => {
          const { flagged, poi_result_id } = original;

          return (
            <ToggleSwitch
              id={`toggle-flagged-${poi_result_id}`}
              label={""}
              checked={flagged}
              onToggle={() => {
                setFlagged({ id: poi_result_id, value: !flagged });
              }}
            />
          );
        },
      },
      {
        Header: "Done",
        accessor: "done" as const,
        sortType: "basic",
        Cell: ({ row: { original } }: Cell<POI>) => {
          const { done, poi_result_id } = original;

          return (
            <ToggleSwitch
              id={`toggle-done-${poi_result_id}`}
              label={""}
              checked={done}
              onToggle={() => setTodo({ id: poi_result_id, value: !done })}
            />
          );
        },
      },
      {
        id: "analysisName",
        Header: "Analysis Name",
        accessor: "analysis_name" as const,
        sortType: "basic",
        sortInverted: true,
      },
      {
        id: "source",
        Header: "Source",
        accessor: (row: POI): string => row.poi.source || "N/A",
        sortType: "basic",
        sortInverted: true,
        Cell: ({ row: { original } }: Cell<POI>) => {
          return original.poi.source ? (
            <code>{original.poi.source}</code>
          ) : (
            "N/A"
          );
        },
      },
      {
        id: "sink",
        Header: "Sink",
        accessor: (row: POI): string => row.poi.sink || "N/A",
        sortType: "basic",
        sortInverted: true,
        Cell: ({ row: { original } }: Cell<POI>) => {
          return original.poi.sink ? <code>{original.poi.sink}</code> : "N/A";
        },
      },
      {
        Header: "Insight",
        accessor: (row: POI): string => row.poi.insight,
        sortType: "basic",
        Cell: ({ row: { original } }: Cell<POI>) => {
          const html = marked.parse(original.poi.insight);
          // WARNING: The insight text comes from us, so we trust it.
          // We should probably use DOMPurify to make this even safer.
          return <div dangerouslySetInnerHTML={{ __html: html }} />;
        },
      },
      {
        Header: "Cards",
        sortType: "basic",
        Cell: ({ row: { original } }: Cell<POI>) => {
          return original.graph_requests.length;
        },
      },
    ],
    [data]
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
  } = useTable<POI>(
    {
      columns,
      data,
      initialState: {
        sortBy: [{ id: "analysisName", desc: false }],
        pageSize: PAGINATION_SIZE_CHOICES[DEFAULT_PAGINATION_CHOICE],
      },
      autoResetSortBy: false,
      autoResetRowState: false,
      autoResetFilters: false,
      autoResetPage: false,
      getRowId: (row: POI) => row.poi_result_id,
    },
    useSortBy,
    usePagination
  );

  const handleAnalysisFilterChange = useCallback(
    ({ target: { value } }: ChangeEvent<HTMLSelectElement>) =>
      setAnalysisFilter(value),
    []
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
      <Container className="POIs m5 h-100" fluid>
        {error && <ErrorAlert errors={[error]} />}
        {builds[0] && <BuildInfo build={builds[0]} />}
        {analysisTasks && <AnalysisTasks analysisTasks={analysisTasks} />}
        <div className="filters">
          <ToggleSwitch
            id="toggle-flagged-pois"
            inline
            label="Hide Flagged POIs"
            onToggle={toggleHidingOfFlaggedPOIs}
            checked={shouldHideFlaggedPOIs}
          />
          <ToggleSwitch
            id="toggle-done-pois"
            inline
            label="Hide Done POIs"
            onToggle={toggleHidingOfDonePOIs}
            checked={shouldHideDonePOIs}
          />
          <Form.Group controlId="analysisNameFilter" className="analysisFilter">
            <Form.Control as="select" onChange={handleAnalysisFilterChange}>
              <option value="">Filter by AnalysisName</option>
              {analysisNames.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </Form.Control>
          </Form.Group>
          <NotebookButton buildId={buildId} binaryName={binaryName} />
          <div className="paginationFilter">
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
              pageSizeChoices={PAGINATION_SIZE_CHOICES}
              setPageSize={setPageSize}
            />
          </div>
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

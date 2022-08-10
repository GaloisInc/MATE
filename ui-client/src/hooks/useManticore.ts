import { useCallback, useEffect, useState } from "react";

import {
  createManticoreExploreTask,
  stopManticoreExploreTask,
  getFlowFinderPOI,
  getManticoreTask,
  mapAnalysisParamsToTask,
  DEFAULT_MANTICORE_MEMORY_LIMIT_MB,
} from "../lib/api";
import type { ManticoreTaskResults } from "../lib/api";
import { useMachineFunctionNodes } from "./api/useMachineFunctionNodes";
import { useBuild } from "./api/useBuild";

import type { Policy } from "../pages/Manticore/PolicySelector";
import type { FlowFinderNode } from "./useFlowFinder";
import type { Constraint } from "../pages/Manticore/ConstraintEditor";
import type { AnalysisResult } from "../pages/Manticore/AnalysisResults";

interface HookParams {
  buildId: string;
  poiId?: string;
}

export interface AnalysisParams {
  objectPolicy?: Policy;
  primitivesPolicy?: Policy;
  constraints?: Constraint[];
}

export const useManticore = ({ buildId, poiId }: HookParams) => {
  const [error, setError] = useState<string | null>(null);
  const [binaryName, setBinaryName] = useState<string | undefined>(undefined);
  const [taskId, setTaskId] = useState<string | undefined>(undefined);
  const [taskResults, setTaskResults] = useState<
    ManticoreTaskResults | undefined
  >(undefined);
  const [analysisParams, setAnalysisParams] = useState<
    AnalysisParams | undefined
  >(undefined);
  const [selectedFunction, setSelectedFunction] = useState<
    FlowFinderNode | undefined
  >(undefined);
  const [memoryLimitMB, setMemoryLimitMB] = useState(
    DEFAULT_MANTICORE_MEMORY_LIMIT_MB
  );
  const [timeLimitSeconds, setTimeLimitSeconds] = useState(0);

  const { functionNodes } = useMachineFunctionNodes({ buildId });
  const { builds } = useBuild({ buildIds: [buildId] });

  // fetch the build's binary name
  useEffect(() => {
    if (builds[0]) {
      setBinaryName(
        builds[0].bitcodeArtifact.attributes.binary_filename as string
      );
    }
  }, [builds]);

  // fetch information about the default function associated with a POI
  useEffect(() => {
    if (poiId) {
      getFlowFinderPOI(poiId).then((poi) => {
        console.log(
          `TODO: Process POI for default function associated with it to pass to "setSelectedFunction"`,
          poi
        );
      });
    }
  }, [poiId]);

  // initiate polling for watching current task
  useEffect(() => {
    let resultPollInterval: NodeJS.Timeout;

    if (taskId) {
      resultPollInterval = setInterval(() => {
        getManticoreTask(taskId)
          .then((results) => {
            setTaskResults(results);
            if (results.state === "completed" || results.state === "failed") {
              clearInterval(resultPollInterval);
            }
          })
          .catch((e: any) => {
            console.error(e);
            setError(e.message);
          });
      }, 1000);
    }

    return () => {
      if (resultPollInterval) clearInterval(resultPollInterval);
    };
  }, [taskId]);

  const runAnalysis = useCallback(() => {
    if (analysisParams || selectedFunction) {
      const taskParams = mapAnalysisParamsToTask(
        memoryLimitMB,
        timeLimitSeconds,
        analysisParams,
        selectedFunction
      );
      setError(null);
      createManticoreExploreTask(taskParams, buildId)
        .then((response) => setTaskId(response.task_id))
        .catch((e: any) => {
          console.error(e);
          setError(e.message);
        });
    }
  }, [
    analysisParams,
    buildId,
    memoryLimitMB,
    selectedFunction,
    timeLimitSeconds,
  ]);

  const stopAnalysis = useCallback(() => {
    if (taskId) {
      setError(null);
      stopManticoreExploreTask(taskId)
        .catch((e: any) => {
          console.error(e);
          setError(e.message);
        });
    }
  }, [
    taskId
  ]);

  const onChangeObjectPolicy = useCallback(
    (policy?: Policy) =>
      setAnalysisParams((prev) => ({ ...prev, objectPolicy: policy })),
    [setAnalysisParams]
  );

  const onChangePrimitivesPolicy = useCallback(
    (policy?: Policy) =>
      setAnalysisParams((prev) => ({ ...prev, primitivesPolicy: policy })),
    [setAnalysisParams]
  );

  const onSelectFunction = useCallback(
    (fns: FlowFinderNode[]) => setSelectedFunction(fns[0]),
    [setSelectedFunction]
  );

  const onAddConstraint = useCallback(
    (c: Constraint) =>
      setAnalysisParams((prev) =>
        prev
          ? {
              ...prev,
              constraints: prev?.constraints?.concat(c) ?? [c],
            }
          : { constraints: [c] }
      ),
    [setAnalysisParams]
  );

  const onUpdateConstraint = useCallback(
    (c: Constraint) =>
      setAnalysisParams((prev) => {
        if (prev) {
          const constraintIdx =
            prev.constraints?.findIndex((p) => p.id === c.id) ??
            prev.constraints?.length ??
            null;

          if (constraintIdx === null || !prev.constraints) {
            return { ...prev, constraints: [c] };
          } else {
            prev.constraints[constraintIdx] = c;
            return prev;
          }
        } else {
          return { constraints: [c] };
        }
      }),
    [setAnalysisParams]
  );

  const onDeleteConstraint = useCallback(
    (c: Constraint) =>
      setAnalysisParams((prev) => {
        if (prev) {
          const constraintIdx =
            prev.constraints?.findIndex((p) => p.id === c.id) ??
            prev.constraints?.length ??
            null;

          if (constraintIdx === null || !prev.constraints) {
            return prev;
          } else {
            prev.constraints.splice(constraintIdx, 1);
            return prev;
          }
        } else {
          return prev;
        }
      }),
    [setAnalysisParams]
  );

  const onChangeMemoryLimit = useCallback(
    (limit: number) => setMemoryLimitMB(limit),
    []
  );

  const onChangeTimeLimit = useCallback(
    (limit: number) => setTimeLimitSeconds(limit),
    []
  );

  return {
    // state
    taskId,
    analysisTaskRunning:
      taskResults?.state === "created" || taskResults?.state === "running",
    binaryName,
    canRunAnalysis:
      selectedFunction &&
      !(taskResults?.state === "running" || taskResults?.state === "created"),
    constraints: analysisParams?.constraints ?? [],
    error,
    functionNodes,
    memoryLimitMB,
    results:
      taskResults?.state === "completed"
        ? taskResults.result.exploration_tree !== null
          ? [taskResults.result.exploration_tree]
          : ([] as AnalysisResult[])
        : undefined,
    selectedFunction,
    taskError:
      taskResults?.state === "failed" ? taskResults.result.log : undefined,
    timeLimitSeconds,
    warnings:
      taskResults?.state === "completed" ? taskResults.result.warnings : [],
    // mutators
    onChangeMemoryLimit,
    onChangeObjectPolicy,
    onChangePrimitivesPolicy,
    onChangeTimeLimit,
    onDeleteConstraint,
    onSelectFunction,
    onAddConstraint,
    onUpdateConstraint,
    runAnalysis,
    stopAnalysis,
  };
};

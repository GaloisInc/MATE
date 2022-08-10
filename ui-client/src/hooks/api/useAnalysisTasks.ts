import { useQuery } from "react-query";

import type { AnalysisTask } from "../../lib/api";
import { getAnalysisTasks } from "../../lib/api";

const STALE_TIME_MS = 1000 * 60 * 10; // 10 minutes
const DEFAULT_POLLING_INTERVAL_MS = 3000;

interface UseAnalysisTasksParams {
  buildId: string;
  pollingIntervalMs?: number;
}

export const useAnalysisTasks = ({
  buildId,
  pollingIntervalMs = DEFAULT_POLLING_INTERVAL_MS,
}: UseAnalysisTasksParams) => {
  const { data, error, isLoading } = useQuery<
    AnalysisTask[],
    Error,
    AnalysisTask[]
  >(["analysisTasks", buildId], () => getAnalysisTasks(buildId), {
    refetchInterval: pollingIntervalMs,
    staleTime: STALE_TIME_MS,
  });

  return {
    analysisTasks: data,
    analysisTasksError: error,
    isLoadingAnalysisTasks: isLoading,
  };
};

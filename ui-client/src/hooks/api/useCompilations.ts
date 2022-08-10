import { useQuery } from "react-query";

import type { BuildCompilation } from "../../lib/api";
import { getCompilations } from "../../lib/api";

const STALE_TIME_MS = 1000 * 60 * 10; // 10 minutes
const DEFAULT_POLLING_INTERVAL_MS = 3000;

interface UseCompilationsParams {
  pollingIntervalMs?: number;
}

export const useCompilations = ({
  pollingIntervalMs = DEFAULT_POLLING_INTERVAL_MS,
}: UseCompilationsParams) => {
  const { data, error } = useQuery<
    BuildCompilation[],
    Error,
    BuildCompilation[]
  >(["compilations"], () => getCompilations(), {
    staleTime: STALE_TIME_MS,
    refetchInterval: pollingIntervalMs,
  });

  return {
    compilations: data,
    compilationsError: error,
  };
};

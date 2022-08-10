import { useQuery } from "react-query";

import type { FlowFinderSnapshot } from "../../lib/api";
import { getFlowFinderSnapshots } from "../../lib/api";

const STALE_TIME_MS = 1000 * 60 * 10; // 10 minutes
const DEFAULT_POLLING_INTERVAL_MS = 3000;

interface UseSnapshotsParams {
  pollingIntervalMs?: number;
}

export const useSnapshots = ({
  pollingIntervalMs = DEFAULT_POLLING_INTERVAL_MS,
}: UseSnapshotsParams) => {
  const { data, error } = useQuery<
    FlowFinderSnapshot[],
    Error,
    FlowFinderSnapshot[]
  >(["snapshots"], () => getFlowFinderSnapshots(), {
    staleTime: STALE_TIME_MS,
    refetchInterval: pollingIntervalMs,
  });

  return {
    snapshots: data,
    snapshotsError: error,
  };
};

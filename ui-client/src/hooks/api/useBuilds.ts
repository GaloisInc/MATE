import { useEffect } from "react";
import { useMutation, useQuery } from "react-query";

import { getBuilds, rebuildWithMinimalSettings } from "../../lib/api";
import type { Build, RebuildApiParams } from "../../lib/api";

const STALE_TIME_MS = 1000 * 60 * 10; // 10 minutes
const DEFAULT_POLLING_INTERVAL_MS = 3000;

interface UseBuildsParams {
  pollingIntervalMs?: number;
}

export const useBuilds = ({
  pollingIntervalMs = DEFAULT_POLLING_INTERVAL_MS,
}: UseBuildsParams) => {
  const {
    data: builds,
    error: buildsError,
    isLoading: isLoadingBuilds,
    refetch: refetchBuilds,
  } = useQuery<Build[], Error, Build[]>(["builds"], () => getBuilds(), {
    refetchInterval: pollingIntervalMs,
    staleTime: STALE_TIME_MS,
  });

  const {
    data: rebuildResult,
    error: rebuildError,
    isLoading: isLoadingRebuild,
    isSuccess: isSuccessRebuild,
    mutate: rebuildBuild,
  } = useMutation((params: RebuildApiParams) =>
    rebuildWithMinimalSettings(params)
  );

  useEffect(() => {
    if (isSuccessRebuild) {
      refetchBuilds();
    }
  }, [isSuccessRebuild, refetchBuilds]);

  return {
    builds,
    buildsError,
    isLoadingBuilds,
    isLoadingRebuild,
    refetchBuilds,
    rebuildBuild,
    rebuildError,
    rebuildResult,
  };
};

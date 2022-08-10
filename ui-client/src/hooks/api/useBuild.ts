import { useQueries } from "react-query";

import type { Build } from "../../lib/api";
import { getBuildById } from "../../lib/api";

const STALE_TIME_MS = 1000 * 60 * 10; // 10 minutes

interface UseBuildParams {
  buildIds: string[];
  isEnabled?: boolean;
}

export const useBuild = ({ buildIds, isEnabled = true }: UseBuildParams) => {
  const results = useQueries<Build[]>(
    buildIds.map((buildId) => ({
      queryKey: ["buildById", buildId],
      queryFn: () => getBuildById(buildId),
      staleTime: STALE_TIME_MS,
      enabled: isEnabled,
    }))
  );

  return {
    builds: results.map<Build>((r) => r.data as Build).filter((b) => b),
    buildsFetchErrors: results.map<Error>((r) => r.error as Error),
    isLoadingBuilds: results.reduce<boolean>(
      (isLoading, r) => isLoading || r.isLoading,
      false
    ),
  };
};

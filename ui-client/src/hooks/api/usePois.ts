import { useEffect, useState } from "react";
import { useMutation, useQuery } from "react-query";

import type {
  POI,
  TogglePOIDoneParams,
  TogglePOIFlaggedParams,
} from "../../lib/api";
import { getPOIs, togglePOIDone, togglePOIFlagged } from "../../lib/api";

const STALE_TIME_MS = 1000 * 60 * 10; // 10 minutes
const DEFAULT_POLLING_INTERVAL_MS = 3000;

interface UsePOIsParams {
  buildId: string;
  pollingIntervalMs?: number;
}

export const usePOIs = ({
  buildId,
  pollingIntervalMs = DEFAULT_POLLING_INTERVAL_MS,
}: UsePOIsParams) => {
  const [isLoadingPOI, setIsLoadingPOI] = useState(true);
  const [poiErrors, setPoiErrors] = useState<Error[]>([]);

  const {
    data: pois,
    error: poisError,
    isLoading: isLoadingPOIs,
    isSuccess: isSuccessPOIs,
    refetch: refetchPOIs,
  } = useQuery<POI[], Error, POI[]>(["pois", buildId], () => getPOIs(buildId), {
    refetchInterval: pollingIntervalMs,
    staleTime: STALE_TIME_MS,
  });

  const {
    error: todoPOIError,
    isLoading: isLoadingTodoPOI,
    isSuccess: isSuccessTodoPOI,
    mutate: togglePOIIsDone,
  } = useMutation<string, Error, TogglePOIDoneParams>(
    (params: TogglePOIDoneParams) => {
      setIsLoadingPOI(true);
      return togglePOIDone(params);
    }
  );

  const {
    error: flaggedPOIError,
    isLoading: isLoadingFlaggedPOI,
    isSuccess: isSuccessFlaggedPOI,
    mutate: togglePOIIsFlagged,
  } = useMutation<string, Error, TogglePOIFlaggedParams>(
    (params: TogglePOIFlaggedParams) => {
      setIsLoadingPOI(true);
      return togglePOIFlagged(params);
    }
  );

  useEffect(() => {
    if (isSuccessTodoPOI || isSuccessFlaggedPOI) {
      setPoiErrors([]);
      refetchPOIs();
    }
  }, [isSuccessFlaggedPOI, isSuccessTodoPOI, refetchPOIs]);

  useEffect(() => {
    const isStillLoadingSomething =
      (isLoadingPOIs && !pois) || isLoadingFlaggedPOI || isLoadingTodoPOI;
    const allSuccessful =
      isSuccessPOIs && isSuccessFlaggedPOI && isSuccessTodoPOI;

    setIsLoadingPOI(isStillLoadingSomething && !allSuccessful);
  }, [
    isLoadingFlaggedPOI,
    isLoadingPOIs,
    isLoadingTodoPOI,
    isSuccessFlaggedPOI,
    isSuccessPOIs,
    isSuccessTodoPOI,
    pois,
  ]);

  useEffect(() => {
    if (poisError || todoPOIError || flaggedPOIError) {
      setPoiErrors(
        [poisError, todoPOIError, flaggedPOIError].filter(
          (e): e is Error => e !== null
        )
      );
    }
  }, [flaggedPOIError, poisError, todoPOIError]);

  return {
    isLoadingPOI,
    poiErrors,
    pois,
    refetchPOIs,
    togglePOIIsDone,
    togglePOIIsFlagged,
  };
};

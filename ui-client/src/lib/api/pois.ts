import { axiosInstance as axiosClient } from "./axios-instance";
import { processResponse } from "./utils";
import type { POIGraphRequestAPIParams } from "./graphs";

export interface POI {
  build_id: string;
  poi_result_id: string;
  analysis_id: string;
  analysis_task_id: string;
  analysis_name: string; // TODO-- maybe use type to list valid values
  poi: {
    source: string;
    sink: string;
    insight: string;
  };
  done: boolean;
  flagged: boolean;
  background?: string;
  graph_requests: POIGraphRequestAPIParams[];
}

export interface FlowFinderPOI {
  insight: string;
  background: string;
  graph_requests: POIGraphRequestAPIParams[];
}

export const getPOIs = async (buildId: string): Promise<POI[]> => {
  return axiosClient.get(`/api/v1/pois/build/${buildId}`).then(processResponse);
};

export interface TogglePOIDoneParams {
  poiId: string;
  isDone: boolean;
}
export const togglePOIDone = async ({
  poiId,
  isDone,
}: TogglePOIDoneParams): Promise<string> => {
  // this api returns null, but react-query creates a cache key for this result,
  // we return the ID of the updated POI
  return axiosClient
    .put(`/api/v1/pois/${poiId}?done=${isDone}`)
    .then(() => poiId);
};

export interface TogglePOIFlaggedParams {
  poiId: string;
  isFlagged: boolean;
}
export const togglePOIFlagged = async ({
  poiId,
  isFlagged,
}: TogglePOIFlaggedParams): Promise<string> => {
  // this api returns null, but react-query creates a cache key for this result,
  // we return the ID of the updated POI
  return axiosClient
    .put(`/api/v1/pois/${poiId}?flagged=${isFlagged}`)
    .then(() => poiId);
};

export const getFlowFinderPOI = async (
  poiId: string
): Promise<FlowFinderPOI> => {
  return axiosClient.get(`/api/v1/pois/${poiId}/detail`).then(processResponse);
};

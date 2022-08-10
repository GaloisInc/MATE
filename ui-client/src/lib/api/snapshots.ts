import { axiosInstance as axiosClient } from "./axios-instance";
import { processResponse } from "./utils";
import type { POIGraphRequestAPIParams } from "./graphs";
import type { GraphId, NodeId } from "../../components/Graph";
import type { FilterChoice } from "../../components/Filters";

export interface FlowFinderAnnotation {
  annotation: string;
  graphId: string;
  createdAt: number;
}

export type FlowFinderAnnotationsByGraphId = Record<
  GraphId,
  FlowFinderAnnotation[]
>;

export interface NewFlowFinderSnapshot {
  user_annotations: FlowFinderAnnotationsByGraphId;
  label: string;
  filters: FilterChoice[];
  graph_requests: POIGraphRequestAPIParams[];
  hidden_graph_ids: GraphId[];
  hidden_node_ids: NodeId[];
  poi_result_id?: string;
}

export interface APIFlowFinderSnapshot extends NewFlowFinderSnapshot {
  build_id: string;
  snapshot_id: string;
}

export interface FlowFinderSnapshot
  extends NewFlowFinderSnapshot,
    APIFlowFinderSnapshot {
  id: string;
}

export const getFlowFinderSnapshotById = async (
  snapshotId: string
): Promise<FlowFinderSnapshot> => {
  return axiosClient
    .get(`/api/v1/snapshots/${snapshotId}`)
    .then(processResponse);
};

export const getFlowFinderSnapshots = async (): Promise<
  FlowFinderSnapshot[]
> => {
  return axiosClient
    .get(`/api/v1/snapshots?detail=true`)
    .then(processResponse)
    .then((snapshots) =>
      snapshots.map((s: APIFlowFinderSnapshot) => ({
        id: s.snapshot_id,
        ...s,
      }))
    );
};

export const createFlowFinderSnapshot = async (
  params: NewFlowFinderSnapshot,
  buildId: string
): Promise<FlowFinderSnapshot> => {
  return params.poi_result_id
    ? axiosClient
        .post(`/api/v1/pois/${params.poi_result_id}/snapshots`, params)
        .then(processResponse)
    : axiosClient
        .post(`/api/v1/snapshots/${buildId}`, params)
        .then(processResponse);
};

import { axiosInstance as axiosClient } from "./axios-instance";
import { processResponse } from "./utils";

export type AnalysisState =
  | "created"
  | "duplicate"
  | "running"
  | "failed"
  | "completed";

export interface AnalysisTask {
  analysis_task_id: string;
  analysis_id: string;
  analysis_name: string;
  build_id: string;
  poi_result_ids: string[];
  state: AnalysisState;
}

export const getAnalysisTasks = async (
  buildId: string
): Promise<AnalysisTask[]> => {
  return axiosClient
    .get(`/api/v1/analyses/tasks/${buildId}?detail=true`)
    .then(processResponse);
};

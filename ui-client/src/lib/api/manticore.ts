import { axiosInstance as axiosClient } from "./axios-instance";
import { processResponse } from "./utils";
import type { AnalysisResult } from "../../pages/Manticore/AnalysisResults";
import type { AnalysisParams } from "../../hooks/useManticore";
import { FlowFinderNode } from "../../hooks/useFlowFinder";

interface ManticoreExploreApiParams {
  docker_memory_limit: number;
  explore_msg: {
    command_line_flags: string[];
    concrete_start: string;
    stdin_size: number;
    env: unknown;
    target_function?: string;
    input_constraints: string[];
    primitive_ptr_policy?: {
      policy_type: "custom" | "default";
      max_alternatives?: number;
      custom_values: number[];
    };
    complex_ptr_policy?: {
      policy_type: "custom" | "default";
      max_alternatives?: number;
      custom_values: number[];
    };
  };
}

type ManticoreTaskKind = "Reachability" | "Explore" | "ExploreFunction";
type ManticoreTaskState = "created" | "running" | "completed" | "failed";

interface ManticoreTaskResult {
  log: string;
  exploration_tree: AnalysisResult | null;
  warnings: string[];
}

interface ManticoreExploreApiResponse {
  task_id: string;
  build_id: string;
  artifact_ids: string[];
  kind: ManticoreTaskKind;
  request: unknown;
  result: unknown;
  state: ManticoreTaskState;
  docker_image: string;
}

interface ManticoreTaskApiResponse {
  task_id: string;
  build_id: string;
  artifact_ids: string[];
  kind: ManticoreTaskKind;
  request: unknown;
  result: ManticoreTaskResult;
  state: ManticoreTaskState;
  docker_image: string;
}

export interface ManticoreTaskResults {
  taskId: string;
  buildId: string;
  kind: ManticoreTaskKind;
  request: unknown;
  result: ManticoreTaskResult;
  state: ManticoreTaskState;
}

const mapManticoreTaskResult = (
  response: ManticoreTaskApiResponse
): ManticoreTaskResults => {
  return {
    taskId: response.task_id,
    buildId: response.build_id,
    state: response.state,
    kind: response.kind,
    request: response.request,
    result: response.result,
  };
};

export const mapAnalysisParamsToTask = (
  memoryLimitMB: number,
  timeLimitSeconds: number,
  analysisParams?: AnalysisParams,
  selectedFunction?: FlowFinderNode
): ManticoreExploreApiParams => {
  return {
    docker_memory_limit:
      memoryLimitMB > 0 ? memoryLimitMB : DEFAULT_MANTICORE_MEMORY_LIMIT_MB,
    explore_msg: {
      command_line_flags: [],
      concrete_start: "",
      stdin_size: 256,
      env: {},
      target_function: selectedFunction?.id ?? "",
      input_constraints:
        analysisParams?.constraints?.flatMap((c) =>
          c.enabled ? c.query.trim().split("\n").filter(n => n) : []
        ) ?? [],
      ...(timeLimitSeconds > 0 ? { timeout: timeLimitSeconds } : null),
      ...(analysisParams?.primitivesPolicy
        ? {
            primitive_ptr_policy: {
              policy_type: analysisParams.primitivesPolicy.policyChoice,
              custom_values: analysisParams.primitivesPolicy.customInputValues,
            },
          }
        : null),
      ...(analysisParams?.objectPolicy
        ? {
            complex_ptr_policy: {
              policy_type: analysisParams.objectPolicy.policyChoice,
              custom_values: analysisParams.objectPolicy.customInputValues,
            },
          }
        : null),
    },
  };
};

export const DEFAULT_MANTICORE_MEMORY_LIMIT_MB = 6000;

export const createManticoreExploreTask = async (
  params: ManticoreExploreApiParams,
  buildId: string
): Promise<ManticoreExploreApiResponse> => {
  return axiosClient
    .post(`/api/v1/manticore/explore-function/${buildId}`, params)
    .then(processResponse);
};

export const stopManticoreExploreTask = async (
  taskId: string
): Promise<ManticoreTaskApiResponse> => {
  return axiosClient
    .patch(`/api/v1/manticore/tasks/${taskId}/stop`)
    .then(processResponse);
};

export const getManticoreTask = async (
  taskId: string
): Promise<ManticoreTaskResults> => {
  return axiosClient
    .get(`/api/v1/manticore/tasks/${taskId}`)
    .then(processResponse)
    .then(mapManticoreTaskResult);
};

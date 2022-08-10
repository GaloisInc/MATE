import { axiosInstance as axiosClient } from "./axios-instance";
import { processResponse } from "./utils";

export type CompilationState =
  | "created"
  | "compiling"
  | "compiled"
  | "failed"
  | "rejected";

export interface CompilationApiResponseItem {
  artifact_ids: string[];
  build_ids: string[];
  compilation_id: string;
  state: CompilationState;
  source_artifact: {
    artifact_id: string;
    attributes: Record<string, string | number | boolean>;
    has_object: boolean;
    kind: string;
  };
  log_artifact: {
    artifact_id: string;
    kind: string;
    has_object: boolean;
    attributes: Record<string, string | number | boolean>;
    build_ids: string[];
    compilation_ids: string[];
  };
}

export interface BuildCompilation {
  id: string;
  sourceArtifact: CompilationSourceArtifact;
  state: CompilationState;
  logArtifact?: CompilationLogArtifact;
}

export interface CompilationSourceArtifact {
  id: string;
  attributes: Record<string, string | number | boolean>;
  hasObject: boolean;
  kind: string;
}

export interface CompilationLogArtifact {
  id: string;
  attributes: Record<string, string | number | boolean>;
  hasObject: boolean;
  kind: string;
}

export const mapApiToCompilation = (
  c: CompilationApiResponseItem
): BuildCompilation => {
  return {
    id: c.compilation_id,
    state: c.state,
    sourceArtifact: {
      id: c.source_artifact.artifact_id,
      attributes: {
        ...c.source_artifact.attributes,
      },
      hasObject: c.source_artifact.has_object,
      kind: c.source_artifact.kind,
    },
    ...(c.log_artifact
      ? {
          logArtifact: {
            id: c.log_artifact.artifact_id,
            attributes: {
              ...c.log_artifact.attributes,
            },
            hasObject: c.log_artifact.has_object,
            kind: c.log_artifact.kind,
          },
        }
      : undefined),
  };
};

export const getCompilations = async (): Promise<BuildCompilation[]> => {
  return axiosClient
    .get("/api/v1/compilations?detail=true")
    .then(processResponse)
    .then((compilations) => compilations.map(mapApiToCompilation));
};

export const getCompilationLog = async (
  logArtifactId: string
): Promise<string> => {
  return axiosClient
    .get(`/api/v1/artifacts/${logArtifactId}/object`)
    .then(processResponse);
};

import { axiosInstance as axiosClient } from "./axios-instance";
import { processResponse } from "./utils";
import { mapApiToCompilation } from "./compilations";
import type {
  BuildCompilation,
  CompilationApiResponseItem,
} from "./compilations";

export type BuildApiResponse = BuildApiResponseItem[];

type BuildAttributes = Record<string | number, string | number | boolean>;
export interface BuildApiResponseItem {
  artifact_ids: string[];
  bitcode_artifact: {
    artifact_id: string;
    attributes: Record<string, string | number | boolean>;
    has_object: boolean;
    kind: string;
  };
  build_id: string;
  compilation: CompilationApiResponseItem;
  options: Record<string, string | number | boolean>;
  state: BuildState;
  mantiserve_task_ids: string[];
  attributes: BuildAttributes;
}

export interface BuildBitcodeArtifact {
  id: string;
  attributes: Record<string, string | number | boolean>;
  hasObject: boolean;
  kind: string;
}

export type BuildState =
  | "created"
  | "building"
  | "inserting"
  | "built"
  | "failed";

export interface Build {
  id: string;
  bitcodeArtifact: BuildBitcodeArtifact;
  compilation: BuildCompilation;
  contextSensitivity: string;
  mergeLibraryBitcode: boolean;
  options: Record<string, string | number | boolean>;
  state: BuildState;
  attributes: BuildAttributes;
}

const mapApiToBuild = (b: BuildApiResponseItem): Build => {
  return {
    id: b.build_id,
    state: b.state,
    contextSensitivity: b.options.context_sensitivity as string,
    mergeLibraryBitcode: b.options.merge_library_bitcode as boolean,
    options: b.options,
    bitcodeArtifact: {
      id: b.bitcode_artifact.artifact_id,
      attributes: {
        ...b.bitcode_artifact.attributes,
      },
      hasObject: b.bitcode_artifact.has_object,
      kind: b.bitcode_artifact.kind,
    },
    compilation: mapApiToCompilation(b.compilation),
    attributes: { ...b.attributes },
  };
};

const mapRebuilds = (builds: Build[]): Build[] => {
  const rebuilds = builds.filter((b) => b.attributes.rebuild_of);

  rebuilds.forEach(({ id, attributes: { rebuild_of } }: Build) => {
    const origIdx = builds.findIndex((b) => b.id === rebuild_of);
    if (origIdx >= 0) {
      builds[origIdx] = {
        ...builds[origIdx],
        attributes: {
          ...builds[origIdx].attributes,
          rebuiltBy: id,
        },
      };
    } else {
      console.error(
        `could not find original build(${rebuild_of}) for rebuild(${id})`
      );
    }
  });

  return builds;
};

export const getBuilds = async (): Promise<Build[]> => {
  return axiosClient
    .get("/api/v1/builds?detail=true")
    .then(processResponse)
    .then((builds) => builds.map(mapApiToBuild))
    .then(mapRebuilds);
};

export interface RebuildApiParams {
  compilationId: string;
  binaryFilename: string;
  buildId: string;
}

export const rebuildWithMinimalSettings = async ({
  compilationId: compilation_id,
  binaryFilename: binary_filename,
  buildId: build_id,
}: RebuildApiParams): Promise<Build> => {
  return axiosClient
    .post(
      `/api/v1/builds/${compilation_id}/build/single?run-all-pois=true&rebuild-of=${build_id}&target=${binary_filename}`,
      {
        pointer_analysis: "unification",
        context_sensitivity: "2-callsite",
        merge_library_bitcode: false,
      }
    )
    .then(processResponse)
    .then(mapApiToBuild);
};

export const getBuildById = async (buildId: string): Promise<Build> => {
  return axiosClient
    .get(`/api/v1/builds/${buildId}`)
    .then(processResponse)
    .then((data) => mapApiToBuild(data));
};

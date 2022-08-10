import { axiosInstance } from "./axios-instance";
import { getBuildById, getBuilds } from "./builds";
import type { BuildApiResponseItem } from "./builds";

export const makeBuildResponse = (
  overrides: Partial<BuildApiResponseItem> = {}
): BuildApiResponseItem => {
  return {
    build_id: "TEST-BUILD-ID",
    bitcode_artifact: {
      artifact_id: "TEST-ARTIFACT-ID",
      attributes: {},
      has_object: false,
      kind: "TEST-ARTIFACT-KIND",
    },
    mantiserve_task_ids: [],
    artifact_ids: ["TEST-ARTIFACT-ID"],
    compilation: {
      compilation_id: "TEST-COMPILATION-ID",
      artifact_ids: ["TEST-ARTIFACT-ID"],
      build_ids: ["TEST-BUILD-ID"],
      state: "compiled",
      source_artifact: {
        kind: "TEST-SOURCE-KIND",
        artifact_id: "TEST-SOURCE-ARTIFACT-ID",
        has_object: false,
        attributes: {},
      },
      log_artifact: {
        artifact_id: "TEST-LOG-ARTIFACT-ID",
        kind: "TEST-LOG-KIND",
        has_object: false,
        attributes: {},
        build_ids: [],
        compilation_ids: [],
      },
    },
    options: {
      context_sensitivity: "TEST-CONTEXT-SENSITIVITY",
      merge_library_bitcode: "TEST-MERGE-VAL",
    },
    state: "inserting",
    attributes: {},
    ...overrides,
  };
};

describe("builds api", () => {
  describe("getBuildById", () => {
    let mockGet: jest.SpyInstance;

    beforeEach(() => {
      mockGet = jest.spyOn(axiosInstance, "get");
      mockGet.mockResolvedValue({
        status: 200,
        data: makeBuildResponse(),
      });
    });

    afterEach(() => {
      jest.clearAllMocks();
    });

    test("should return Build object for successful request", () => {
      return expect(getBuildById("TEST-ID")).resolves.toEqual({
        bitcodeArtifact: {
          attributes: {},
          hasObject: false,
          id: "TEST-ARTIFACT-ID",
          kind: "TEST-ARTIFACT-KIND",
        },
        compilation: {
          id: "TEST-COMPILATION-ID",
          sourceArtifact: {
            attributes: {},
            hasObject: false,
            id: "TEST-SOURCE-ARTIFACT-ID",
            kind: "TEST-SOURCE-KIND",
          },
          state: "compiled",
          logArtifact: {
            id: "TEST-LOG-ARTIFACT-ID",
            kind: "TEST-LOG-KIND",
            hasObject: false,
            attributes: {},
          },
        },
        contextSensitivity: "TEST-CONTEXT-SENSITIVITY",
        id: "TEST-BUILD-ID",
        mergeLibraryBitcode: "TEST-MERGE-VAL",
        options: {
          context_sensitivity: "TEST-CONTEXT-SENSITIVITY",
          merge_library_bitcode: "TEST-MERGE-VAL",
        },
        state: "inserting",
        attributes: {},
      });
    });
  });

  describe("getBuilds", () => {
    describe("when making call with a rebuild", () => {
      let mockGet: jest.SpyInstance;

      beforeEach(() => {
        mockGet = jest.spyOn(axiosInstance, "get");
        mockGet.mockResolvedValue({
          status: 200,
          data: [
            makeBuildResponse({ build_id: "TEST-BUILD" }),
            makeBuildResponse({
              build_id: "TEST-REBUILD",
              attributes: { rebuild_of: "TEST-BUILD" },
            }),
          ],
        });
      });

      afterEach(() => jest.clearAllMocks());

      test("should indicate the TEST-BUILD was rebuilt by TEST-REBUILD", () => {
        return expect(getBuilds()).resolves.toEqual([
          {
            id: "TEST-BUILD",
            bitcodeArtifact: {
              id: "TEST-ARTIFACT-ID",
              attributes: {},
              hasObject: false,
              kind: "TEST-ARTIFACT-KIND",
            },
            compilation: {
              id: "TEST-COMPILATION-ID",
              state: "compiled",
              sourceArtifact: {
                kind: "TEST-SOURCE-KIND",
                id: "TEST-SOURCE-ARTIFACT-ID",
                hasObject: false,
                attributes: {},
              },
              logArtifact: {
                id: "TEST-LOG-ARTIFACT-ID",
                kind: "TEST-LOG-KIND",
                hasObject: false,
                attributes: {},
              },
            },
            options: {
              context_sensitivity: "TEST-CONTEXT-SENSITIVITY",
              merge_library_bitcode: "TEST-MERGE-VAL",
            },
            contextSensitivity: "TEST-CONTEXT-SENSITIVITY",
            mergeLibraryBitcode: "TEST-MERGE-VAL",
            state: "inserting",
            attributes: {
              rebuiltBy: "TEST-REBUILD",
            },
          },
          {
            id: "TEST-REBUILD",
            bitcodeArtifact: {
              id: "TEST-ARTIFACT-ID",
              attributes: {},
              hasObject: false,
              kind: "TEST-ARTIFACT-KIND",
            },
            compilation: {
              id: "TEST-COMPILATION-ID",
              state: "compiled",
              sourceArtifact: {
                kind: "TEST-SOURCE-KIND",
                id: "TEST-SOURCE-ARTIFACT-ID",
                hasObject: false,
                attributes: {},
              },
              logArtifact: {
                id: "TEST-LOG-ARTIFACT-ID",
                kind: "TEST-LOG-KIND",
                hasObject: false,
                attributes: {},
              },
            },
            options: {
              context_sensitivity: "TEST-CONTEXT-SENSITIVITY",
              merge_library_bitcode: "TEST-MERGE-VAL",
            },
            contextSensitivity: "TEST-CONTEXT-SENSITIVITY",
            mergeLibraryBitcode: "TEST-MERGE-VAL",
            state: "inserting",
            attributes: { rebuild_of: "TEST-BUILD" },
          },
        ]);
      });
    });
  });
});

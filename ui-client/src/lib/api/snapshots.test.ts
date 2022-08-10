import { axiosInstance } from "./axios-instance";
import { createFlowFinderSnapshot } from "./snapshots";

describe("snapshots api", () => {
  describe("createFlowFinderSnapshot", () => {
    let mockPost: jest.SpyInstance;

    beforeEach(() => {
      mockPost = jest.spyOn(axiosInstance, "post");
      mockPost.mockResolvedValueOnce({});
    });

    afterEach(() => jest.clearAllMocks());

    test("should call the basic 'snapshots' endpoint when no POI provided", () => {
      createFlowFinderSnapshot(
        {
          user_annotations: [],
          filters: [],
          graph_requests: [],
          hidden_graph_ids: [],
          hidden_node_ids: [],
          label: "TEST",
        },
        "TEST-BUILD"
      );
      expect(mockPost.mock.calls[0][0]).toEqual("/api/v1/snapshots/TEST-BUILD");
    });

    test("should call the poi 'snapshots' endpoint when POI provided", () => {
      createFlowFinderSnapshot(
        {
          user_annotations: [],
          filters: [],
          graph_requests: [],
          hidden_graph_ids: [],
          hidden_node_ids: [],
          label: "TEST",
          poi_result_id: "TEST-POI",
        },
        "TEST-BUILD"
      );
      expect(mockPost.mock.calls[0][0]).toEqual(
        "/api/v1/pois/TEST-POI/snapshots"
      );
    });
  });
});

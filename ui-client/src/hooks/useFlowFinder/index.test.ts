import { renderHook } from "@testing-library/react-hooks";
import axios from "axios";
import type { AxiosResponse } from "axios";
import { axiosInstance } from "../../lib/api/axios-instance";
import { createQueryWrapper } from "../../testUtils";
import { useFlowFinder } from ".";
import {
  generateGraphKey,
  parseGraphKey,
  generateSliceKey,
  parseSliceKey,
  generateNodeKey,
  parseNodeKey,
} from "./keyTools";
import { makeBuildResponse } from "../../lib/api/builds.test";
import { makeFunctionNodesResponse } from "../../lib/api/graphs.test";
import type {
  GraphApiParams,
  GraphSliceApiParams,
  NodeApiParams,
} from "../../lib/api";

// since our hook makes a lot of api calls, we need to mock that out
jest.mock("../../lib/api/axios-instance");
const mockedAxios = axiosInstance as jest.Mocked<typeof axios>;

// since we log api errors to console.error, trap those messages
jest.spyOn(global.console, "error");

function makeMockResponse(
  data: any = undefined,
  status: number = 200,
  statusText: string = "OK"
): AxiosResponse {
  return {
    status,
    statusText,
    data,
    headers: {},
    config: {},
  };
}

describe("useFlowFinder", () => {
  const TEST_BUILD_ID = "TEST-BUILD-ID";
  const TEST_POI_ID = "TEST-POI-ID";
  const TEST_NODE_ID = "TEST-NODE-ID";
  const TEST_SOURCE_ID = "TEST-SOURCE-ID";

  describe("when initial API call fails", () => {
    beforeEach(() => {
      mockedAxios.get.mockResolvedValue(
        makeMockResponse({}, 500, "GET TEST ERROR")
      );
    });

    afterEach(() => {
      mockedAxios.get.mockReset();
    });

    test("hook should return an error message", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.error).toBe("Unable to fetch: GET TEST ERROR");
    });
  });

  describe("when initial API calls pass", () => {
    beforeEach(() => {
      mockedAxios.get
        .mockResolvedValueOnce(makeMockResponse(makeFunctionNodesResponse()))
        .mockResolvedValueOnce(makeMockResponse(makeBuildResponse()));
    });

    afterEach(() => mockedAxios.get.mockReset());

    test("hook should not return an error message", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.error).toBe(null);
    });

    test("hook should return isLoading value that indicates we are no longer loading", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.isLoading).toBeFalsy();
    });

    test("hook should return a list of functionNodes", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.functionNodes).toEqual([
        {
          data: {
            function_id: "function:<foo>",
            graphIds: [],
            id: "TEST-FOO-NODE-ID",
            isParent: true,
            label: "test foo label",
            node_id: "TEST-FOO-NODE-ID",
            node_kind: "Function",
            opcode: "None",
            parent: "TEST-SOURCE-ID",
            source_id: "TEST-SOURCE-ID",
          },
          id: "TEST-FOO-NODE-ID",
        },
        {
          data: {
            function_id: "function:<bar>",
            graphIds: [],
            id: "TEST-BAR-NODE-ID",
            isParent: true,
            label: "test bar label",
            node_id: "TEST-BAR-NODE-ID",
            node_kind: "Function",
            opcode: "None",
            parent: "TEST-SOURCE-ID",
            source_id: "TEST-SOURCE-ID",
          },
          id: "TEST-BAR-NODE-ID",
        },
      ]);
    });

    test("hook should return empty nodeCache", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.nodeCache).toEqual({});
    });

    test("hook should return empty graphCache", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.graphCache).toEqual({});
    });

    test("hook should return empty graphSliceCache", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.graphSliceCache).toEqual({});
    });

    test("hook should return empty mergedGraph", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.mergedGraphs).toEqual([]);
    });

    test("hook should indicate resizing of graph is not paused", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.pauseGraphResize).toBeFalsy();
    });

    test("hook should indicate context menu should not be shown", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.shouldShowContextMenu).toBeFalsy();
    });

    test("hook should not return a sourceId", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.sourceId).toBeUndefined();
    });

    test("hook should not return a sinkId", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.sinkId).toBeUndefined();
    });

    test("hook should return filter list indicating memory nodes should be hidden", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.filters).toEqual(["MemoryLocation"]);
    });

    test("hook should not return a background", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.background).toBeUndefined();
    });

    test("hook should not return an insight", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.insight).toBeUndefined();
    });

    test("hook should return default mouse coordinates", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.mouseCoord).toEqual({ x: 0, y: 0 });
    });

    test("hook should return empty list of hidden graph ids", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.hiddenGraphIds).toHaveLength(0);
    });

    test("hook should return empty list of hidden node ids", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.hiddenNodeIds.size).toEqual(0);
    });

    test("hook should return no graph to highlight", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.highlightedGraphId).toBeUndefined();
    });

    test("hook should return no analysis graph", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.analysisGraphId).toBeUndefined();
    });

    test("hook should return no analysis nodes", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.analysisNodesById).toEqual({});
    });
  });

  describe("when there is a POI passed in", () => {
    beforeEach(() => {
      mockedAxios.get.mockImplementation((url) => {
        switch (url) {
          case `/api/v1/graphs/${TEST_BUILD_ID}/function-nodes`:
            return Promise.resolve(
              makeMockResponse(makeFunctionNodesResponse())
            );
          case `/api/v1/pois/${TEST_POI_ID}/detail`:
            return Promise.resolve(
              makeMockResponse({
                insight: "TEST INSIGHT",
                background: "TEST BACKGROUND",
                graph_requests: [
                  {
                    build_id: TEST_BUILD_ID,
                    node_id: TEST_NODE_ID,
                    request_kind: "node",
                  },
                  {
                    build_id: TEST_BUILD_ID,
                    origin_node_ids: [TEST_NODE_ID],
                    kind: "callsites",
                    request_kind: "graph",
                  },
                  {
                    build_id: TEST_BUILD_ID,
                    sink_id: TEST_NODE_ID,
                    source_id: TEST_SOURCE_ID,
                    kind: "callsites",
                    request_kind: "slice",
                  },
                ],
              })
            );
          case `/api/v1/graphs/${TEST_BUILD_ID}/nodes/${TEST_NODE_ID}`:
            return Promise.resolve(
              makeMockResponse({
                nodes: [
                  {
                    node_id: TEST_NODE_ID,
                    node_kind: "function",
                    opcode: "None",
                    function_id: "None",
                    label: "test node",
                    source_id: TEST_SOURCE_ID,
                  },
                ],
                edges: [],
              })
            );
          case `/api/v1/builds/${TEST_BUILD_ID}`:
            return Promise.resolve(makeMockResponse(makeBuildResponse()));
          default:
            return Promise.reject(new Error(`UNKNOWN GET URL: ${url}`));
        }
      });
      mockedAxios.post.mockImplementation((url, params) => {
        switch (url) {
          case `/api/v1/graphs/${TEST_BUILD_ID}`:
            return Promise.resolve(
              makeMockResponse({
                nodes: [
                  {
                    function_id: "None",
                    label: "test node",
                    node_id: "TEST-NODE-ID",
                    node_kind: "function",
                    opcode: "None",
                    source_id: "TEST-SOURCE-ID",
                  },
                  {
                    function_id: "None",
                    label: "test node 2",
                    node_id: "TEST-NODE2-ID",
                    node_kind: "function",
                    opcode: "None",
                    source_id: "TEST-SOURCE-ID",
                  },
                ],
                edges: [
                  {
                    edge_id: "TEST-EDGE-ID",
                    edge_kind: "TEST-EDGE-KIND",
                    source_id: "TEST-NODE-ID",
                    target_id: "TEST-NODE2-ID",
                  },
                ],
              })
            );
          case `/api/v1/graphs/${TEST_BUILD_ID}/slices`:
            return Promise.resolve(
              makeMockResponse({
                nodes: [
                  {
                    function_id: "None",
                    label: "test node",
                    node_id: "TEST-NODE-ID",
                    node_kind: "function",
                    opcode: "None",
                    source_id: "TEST-SOURCE-ID",
                  },
                  {
                    function_id: "None",
                    label: "test node 2",
                    node_id: "TEST-NODE2-ID",
                    node_kind: "function",
                    opcode: "None",
                    source_id: "TEST-SOURCE-ID",
                  },
                ],
                edges: [
                  {
                    edge_id: "TEST-EDGE-ID",
                    edge_kind: "TEST-EDGE-KIND",
                    source_id: "TEST-NODE-ID",
                    target_id: "TEST-NODE2-ID",
                  },
                ],
              })
            );
          default:
            return Promise.reject(new Error(`UNKNOWN POST URL: ${url}`));
        }
      });
    });

    afterEach(() => {
      mockedAxios.get.mockReset();
      mockedAxios.post.mockReset();
    });

    test("hook should return nodeCache", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID, poiId: TEST_POI_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.nodeCache).toEqual({
        [generateNodeKey({ build_id: TEST_BUILD_ID, node_id: TEST_NODE_ID })]: {
          edges: [],
          nodes: [
            {
              function_id: "None",
              label: "test node",
              node_id: "TEST-NODE-ID",
              node_kind: "function",
              opcode: "None",
              source_id: "TEST-SOURCE-ID",
            },
          ],
        },
      });
    });

    test("hook should return graphCache", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID, poiId: TEST_POI_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.graphCache).toEqual({
        [generateGraphKey({
          build_id: TEST_BUILD_ID,
          kind: "callsites",
          origin_node_ids: [TEST_NODE_ID],
        })]: {
          edges: [
            {
              id: "TEST-NODE-ID​TEST-NODE2-ID​TEST-EDGE-KIND",
              edge_id: "TEST-EDGE-ID",
              edge_kind: "TEST-EDGE-KIND",
              kind: "TEST-EDGE-KIND",
              source_id: "TEST-NODE-ID",
              target_id: "TEST-NODE2-ID",
            },
          ],
          kind: "callsites",
          nodes: [
            {
              function_id: "None",
              label: "test node",
              node_id: "TEST-NODE-ID",
              node_kind: "function",
              opcode: "None",
              source_id: "TEST-SOURCE-ID",
            },
            {
              function_id: "None",
              label: "test node 2",
              node_id: "TEST-NODE2-ID",
              node_kind: "function",
              opcode: "None",
              source_id: "TEST-SOURCE-ID",
            },
          ],
          originNodeIds: ["TEST-NODE-ID"],
        },
      });
    });

    test("hook should return graphSliceCache", async () => {
      const { result, waitForNextUpdate } = renderHook(
        () => useFlowFinder({ buildId: TEST_BUILD_ID, poiId: TEST_POI_ID }),
        {
          wrapper: createQueryWrapper(),
        }
      );
      await waitForNextUpdate();
      expect(result.current.graphSliceCache).toEqual({
        [generateSliceKey({
          build_id: TEST_BUILD_ID,
          source_id: TEST_SOURCE_ID,
          kind: "callsites",
          sink_id: TEST_NODE_ID,
        })]: {
          avoidNodeIds: [],
          focusNodeIds: [],
          edges: [
            {
              id: "TEST-NODE-ID​TEST-NODE2-ID​TEST-EDGE-KIND",
              edge_id: "TEST-EDGE-ID",
              edge_kind: "TEST-EDGE-KIND",
              kind: "TEST-EDGE-KIND",
              source_id: "TEST-NODE-ID",
              target_id: "TEST-NODE2-ID",
            },
          ],
          kind: "callsites",
          nodes: [
            {
              function_id: "None",
              label: "test node",
              node_id: "TEST-NODE-ID",
              node_kind: "function",
              opcode: "None",
              source_id: "TEST-SOURCE-ID",
            },
            {
              function_id: "None",
              label: "test node 2",
              node_id: "TEST-NODE2-ID",
              node_kind: "function",
              opcode: "None",
              source_id: "TEST-SOURCE-ID",
            },
          ],
          sink: TEST_NODE_ID,
          source: TEST_SOURCE_ID,
        },
      });
    });
  });

  describe("graph key generation/parsing", () => {
    test("should return the original api params when parsing key generated from those params", () => {
      const params: GraphApiParams = {
        build_id: "TEST-ID",
        kind: "callees",
        origin_node_ids: ["TEST-ORIGIN-ID-1", "TEST-ORIGIN-ID-2"],
      };
      expect(parseGraphKey(generateGraphKey(params))).toEqual(params);
    });

    test("should gracefully handle when no origin_node_ids", () => {
      const params: GraphApiParams = {
        build_id: "TEST-ID",
        kind: "callees",
        origin_node_ids: [],
      };
      expect(parseGraphKey(generateGraphKey(params))).toEqual(params);
    });
  });

  describe("graph slice key generation/parsing", () => {
    test("should return the original api params when parsing key generated from those params", () => {
      const params: GraphSliceApiParams = {
        build_id: "TEST-ID",
        kind: "callees",
        source_id: "TEST-SOURCE-ID",
        sink_id: "TEST-SINK-ID",
        focus_node_ids: ["TEST-FOCUS-ID-1", "TEST-FOCUS-ID-2"],
        avoid_node_ids: ["TEST-AVOID-ID-1", "TEST-AVOID-ID-2"],
      };
      expect(parseSliceKey(generateSliceKey(params))).toEqual(params);
    });

    test("should gracefully handle missing optional params", () => {
      const params: GraphSliceApiParams = {
        build_id: "TEST-ID",
        kind: "callees",
        source_id: "TEST-SOURCE-ID",
        sink_id: "TEST-SINK-ID",
      };
      expect(parseSliceKey(generateSliceKey(params))).toEqual(params);
    });
  });

  describe("node key generation/parsing", () => {
    test("should return the original api params when parsing key generated from those params", () => {
      const params: NodeApiParams = {
        build_id: "TEST-ID",
        node_id: "TEST-NODE-ID",
      };
      expect(parseNodeKey(generateNodeKey(params))).toEqual(params);
    });

    test("should gracefully handle empty strings", () => {
      const params: NodeApiParams = {
        build_id: "",
        node_id: "",
      };
      expect(parseNodeKey(generateNodeKey(params))).toEqual(params);
    });
  });
});

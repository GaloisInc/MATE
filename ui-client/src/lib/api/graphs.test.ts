import { axiosInstance } from "./axios-instance";
import { getFunctionNodes } from "./graphs";
import type { ApiNode } from "./graphs";

export const makeFunctionNodesResponse = (): ApiNode[] => {
  return [
    {
      node_id: "TEST-FOO-NODE-ID",
      node_kind: "Function",
      opcode: "None",
      label: "test foo label",
      source_id: "TEST-SOURCE-ID",
      function_id: "function:<foo>",
    },
    {
      node_id: "TEST-BAR-NODE-ID",
      node_kind: "Function",
      opcode: "None",
      label: "test bar label",
      source_id: "TEST-SOURCE-ID",
      function_id: "function:<bar>",
    },
  ];
};

describe("graphs api", () => {
  describe("getFunctionNodes", () => {
    let mockGet: jest.SpyInstance;

    beforeEach(() => {
      mockGet = jest.spyOn(axiosInstance, "get");
      mockGet.mockResolvedValue({
        status: 200,
        data: makeFunctionNodesResponse(),
      });
    });

    afterEach(() => {
      jest.clearAllMocks();
    });

    test("should return list of function ApiNodes for successful request", () => {
      return expect(getFunctionNodes("TEST-BUILD-ID")).resolves.toEqual([
        {
          function_id: "function:<foo>",
          label: "test foo label",
          node_id: "TEST-FOO-NODE-ID",
          node_kind: "Function",
          opcode: "None",
          source_id: "TEST-SOURCE-ID",
        },
        {
          function_id: "function:<bar>",
          label: "test bar label",
          node_id: "TEST-BAR-NODE-ID",
          node_kind: "Function",
          opcode: "None",
          source_id: "TEST-SOURCE-ID",
        },
      ]);
    });
  });
});

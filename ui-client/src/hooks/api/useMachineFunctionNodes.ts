import { useQuery } from "react-query";

import type { FlowFinderNode } from "../useFlowFinder";
import { mapApiNodeToFlowFinderNode } from "../useFlowFinder";
import { getMachineFunctionNodes } from "../../lib/api";

const STALE_TIME_MS = 1000 * 60 * 10; // 10 minutes

interface UseFunctionNodesParams {
  buildId: string;
}

export const useMachineFunctionNodes = ({ buildId }: UseFunctionNodesParams) => {
  const { data, error } = useQuery<FlowFinderNode[], Error, FlowFinderNode[]>(
    ["machineFunctionNodes", buildId],
    () =>
      getMachineFunctionNodes(buildId).then((nodes) =>
        nodes.map(mapApiNodeToFlowFinderNode)
      ),
    { staleTime: STALE_TIME_MS }
  );

  return {
    functionNodes: data,
    functionNodeError: error,
  };
};

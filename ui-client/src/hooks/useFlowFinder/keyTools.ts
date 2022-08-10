import {
  GraphApiParams,
  GraphSliceApiParams,
  GraphType,
  NodeApiParams,
} from "../../lib/api";

/**
 * Storing/retrieving API parameters used in graph/slice/node requests
 *
 * Given that we are saving a "snapshot" of a user's analysis in the flow-finder and
 * that we are generating unique keys for each graph/slice/node returned for a given
 * API request, we are combining these two features by serializing the API parameters
 * into a string that is then used as the key to save the API request in state.
 *
 * When it comes time to save all API requests that went into creating an analysis as
 * a snapshot, we then parse those keys to extract the API request parameters back out.
 *
 * The below constants are a hack that allow us to safely (de)serialize the API parameter
 * values. By using zero-width Unicode characters as the separators for keys/values,
 * we have relative safety that we those characters will no collide with the characters
 * used in the actual data.
 */
const TOP_LEVEL_KEY_SPLIT_TOKEN = "\u200B"; // Zero-width space (figure we'll never have this as a character...)
const SECOND_LEVEL_KEY_SPLIT_TOKEN = "\u200D"; // Zero-width joiner (figure we'll never have this as a character...)

export const generateGraphKey = ({
  build_id,
  kind,
  origin_node_ids,
}: GraphApiParams) =>
  [build_id, kind, origin_node_ids.join(SECOND_LEVEL_KEY_SPLIT_TOKEN)].join(
    TOP_LEVEL_KEY_SPLIT_TOKEN
  );

export const parseGraphKey = (key: string): GraphApiParams => {
  const [build_id, kind, ids] = key.split(TOP_LEVEL_KEY_SPLIT_TOKEN);

  return {
    build_id,
    kind: kind as GraphType,
    origin_node_ids: ids
      .split(SECOND_LEVEL_KEY_SPLIT_TOKEN)
      .filter((id) => id.length > 0),
  };
};

export const generateSliceKey = ({
  build_id,
  source_id,
  sink_id,
  kind,
  focus_node_ids = [],
  avoid_node_ids = [],
}: GraphSliceApiParams) =>
  [
    build_id,
    source_id,
    sink_id,
    kind,
    focus_node_ids.join(SECOND_LEVEL_KEY_SPLIT_TOKEN),
    avoid_node_ids.join(SECOND_LEVEL_KEY_SPLIT_TOKEN),
  ].join(TOP_LEVEL_KEY_SPLIT_TOKEN);

export const parseSliceKey = (key: string): GraphSliceApiParams => {
  const [build_id, source_id, sink_id, kind, focus_ids, avoid_ids] = key.split(
    TOP_LEVEL_KEY_SPLIT_TOKEN
  );
  let params: GraphSliceApiParams = {
    build_id,
    source_id,
    sink_id,
    kind: kind as GraphType,
  };

  if (focus_ids) {
    params.focus_node_ids = focus_ids.split(SECOND_LEVEL_KEY_SPLIT_TOKEN);
  }

  if (avoid_ids) {
    params.avoid_node_ids = avoid_ids.split(SECOND_LEVEL_KEY_SPLIT_TOKEN);
  }

  return params;
};

export const generateNodeKey = ({ build_id, node_id }: NodeApiParams) =>
  [build_id, node_id].join(TOP_LEVEL_KEY_SPLIT_TOKEN);

export const parseNodeKey = (key: string): NodeApiParams => {
  const [build_id, node_id] = key.split(TOP_LEVEL_KEY_SPLIT_TOKEN);
  return { build_id, node_id };
};

import { GraphData, NodeData, EdgeData } from "./types";

export const testGraphs: Record<string, GraphData<NodeData, EdgeData>> = {
  SIMPLE: {
    id: "SIMPLE",
    nodes: [
      {
        id: "SIMPLE-HEAD",
        data: {
          id: "SIMPLE-HEAD",
          isParent: false,
        },
      },
      {
        id: "SIMPLE-CHILD",
        data: {
          id: "SIMPLE-CHILD",
          isParent: false,
        },
      },
      {
        id: "SIMPLE-TAIL",
        data: {
          id: "SIMPLE-TAIL",
          isParent: false,
        },
      },
    ],
    edges: [
      {
        id: "SIMPLE-HEAD-SIMPLE-CHILD",
        data: {
          id: "SIMPLE-HEAD-SIMPLE-CHILD",
          source: "SIMPLE-HEAD",
          target: "SIMPLE-CHILD",
        },
      },
      {
        id: "SIMPLE-CHILD-SIMPLE-TAIL",
        data: {
          id: "SIMPLE-CHILD-SIMPLE-TAIL",
          source: "SIMPLE-CHILD",
          target: "SIMPLE-TAIL",
        },
      },
    ],
  },
  "SIMPLE-MULT-OUT": {
    id: "SIMPLE-MULT-OUT",
    nodes: [
      {
        id: "SIMPLE-HEAD",
        data: {
          id: "SIMPLE-HEAD",
          isParent: false,
        },
      },
      {
        id: "SIMPLE-CHILD",
        data: {
          id: "SIMPLE-CHILD",
          isParent: false,
        },
      },
      {
        id: "SIMPLE-TAIL-ONE",
        data: {
          id: "SIMPLE-TAIL-ONE",
          isParent: false,
        },
      },
      {
        id: "SIMPLE-TAIL-TWO",
        data: {
          id: "SIMPLE-TAIL-TWO",
          isParent: false,
        },
      },
    ],
    edges: [
      {
        id: "SIMPLE-HEAD-SIMPLE-CHILD",
        data: {
          id: "SIMPLE-HEAD-SIMPLE-CHILD",
          source: "SIMPLE-HEAD",
          target: "SIMPLE-CHILD",
        },
      },
      {
        id: "SIMPLE-CHILD-SIMPLE-TAIL-ONE",
        data: {
          id: "SIMPLE-CHILD-SIMPLE-TAIL-ONE",
          source: "SIMPLE-CHILD",
          target: "SIMPLE-TAIL-ONE",
        },
      },
      {
        id: "SIMPLE-CHILD-SIMPLE-TAIL-TWO",
        data: {
          id: "SIMPLE-CHILD-SIMPLE-TAIL-TWO",
          source: "SIMPLE-CHILD",
          target: "SIMPLE-TAIL-TWO",
        },
      },
    ],
  },
  "HAS-CHILDREN": {
    id: "HAS-CHILDREN",
    nodes: [
      {
        id: "HC-HEAD",
        data: {
          id: "HC-HEAD",
          isParent: false,
        },
      },
      {
        id: "HC-PARENT",
        data: {
          id: "HC-PARENT",
          isParent: true,
        },
      },
      {
        id: "HC-CHILD",
        data: {
          id: "HC-CHILD",
          isParent: false,
          parent: "HC-PARENT",
        },
      },
      {
        id: "HC-TAIL",
        data: {
          id: "HC-TAIL",
          isParent: false,
        },
      },
    ],
    edges: [
      {
        id: "HC-HEAD-HC-CHILD",
        data: {
          id: "HC-HEAD-HC-CHILD",
          source: "HC-HEAD",
          target: "HC-CHILD",
        },
      },
      {
        id: "HC-CHILD-HC-TAIL",
        data: {
          id: "HC-CHILD-HC-TAIL",
          source: "HC-CHILD",
          target: "HC-TAIL",
        },
      },
    ],
  },
  DEEP: {
    id: "FOUR-LAYER",
    nodes: [
      {
        id: "DEEP-HEAD",
        data: {
          id: "DEEP-HEAD",
          isParent: false,
        },
      },
      {
        id: "DEEP-CHILD",
        data: {
          id: "DEEP-CHILD",
          isParent: false,
        },
      },
      {
        id: "DEEP-GRANDCHILD",
        data: {
          id: "DEEP-GRANDCHILD",
          isParent: false,
        },
      },
      {
        id: "DEEP-GREAT-GRANDCHILD-CHILD",
        data: {
          id: "DEEP-GREAT-GRANDCHILD-CHILD",
          isParent: false,
        },
      },
      {
        id: "DEEP-GREAT-GRANDCHILD",
        data: {
          id: "DEEP-GREAT-GRANDCHILD",
          isParent: false,
        },
      },
      {
        id: "DEEP-TAIL",
        data: {
          id: "DEEP-TAIL",
          isParent: false,
        },
      },
    ],
    edges: [
      {
        id: "DEEP-HEAD-DEEP-CHILD",
        data: {
          id: "DEEP-HEAD-DEEP-CHILD",
          source: "DEEP-HEAD",
          target: "DEEP-CHILD",
        },
      },
      {
        id: "DEEP-CHILD-DEEP-GRANDCHILD",
        data: {
          id: "DEEP-CHILD-DEEP-GRANDCHILD",
          source: "DEEP-CHILD",
          target: "DEEP-GRANDCHILD",
        },
      },
      {
        id: "DEEP-GRANDCHILD-DEEP-GREAT-GRANDCHILD",
        data: {
          id: "DEEP-GRANDCHILD-DEEP-GREAT-GRANDCHILD",
          source: "DEEP-GRANDCHILD",
          target: "DEEP-GREAT-GRANDCHILD",
        },
      },
      {
        id: "DEEP-GREAT-GRANDCHILD-DEEP-GREAT-GRANDCHILD-CHILD",
        data: {
          id: "DEEP-GREAT-GRANDCHILD-DEEP-GREAT-GRANDCHILD-CHILD",
          source: "DEEP-GREAT-GRANDCHILD",
          target: "DEEP-GREAT-GRANDCHILD-CHILD",
        },
      },
      {
        id: "DEEP-GREAT-GRANDCHILD-DEEP-TAIL",
        data: {
          id: "DEEP-GREAT-GRANDCHILD-DEEP-TAIL",
          source: "DEEP-GREAT-GRANDCHILD",
          target: "DEEP-TAIL",
        },
      },
    ],
  },
};

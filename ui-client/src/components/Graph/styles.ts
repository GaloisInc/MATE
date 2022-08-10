import { Stylesheet } from "cytoscape";

export const FILTER_CLASS = "filtered";
export const UNFILTER_CLASS = "unfiltered";
export const COLLAPSED_CLASS = "collapsed";
export const HIDDEN_CLASS = "hidden";
export const ADDED_EDGE_CLASS = "added-edge";
export const HIGHLIGHTED_CLASS = "highlighted";

export const baseStyles: Stylesheet[] = [
  {
    selector: "node.highlighted",
    style: {
      "border-color": "#ffc107",
      "border-width": (ele) => Math.max(4 / ele.cy().zoom(), 2),
    },
  },
  {
    selector: "edge.highlighted",
    style: {
      "line-color": "#ffc107",
      "target-arrow-color": "#ffc107",
    },
  },
  {
    selector: `.${HIDDEN_CLASS}`,
    style: {
      display: "none",
    },
  },
  {
    selector: `.${FILTER_CLASS}`,
    style: {
      display: "none",
    },
  },
  {
    selector: `.${COLLAPSED_CLASS}`,
    style: {
      display: "none",
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-color": "#eb3434",
      "border-width": 3,
    },
  },
];

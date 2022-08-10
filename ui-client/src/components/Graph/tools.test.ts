import { Graph as GraphLib } from "graphlib";
import { NodeId } from "./types";
import { buildGraph } from "./tools";
import { testGraphs } from "./test-graphs";

describe("Graph/tools", () => {
  describe("buildGraph", () => {
    describe("single graph build", () => {
      const hiddenIds: Set<NodeId> = new Set();
      const graphs = [testGraphs["SIMPLE"]];
      let graph: GraphLib;

      beforeEach(() => {
        graph = buildGraph(graphs, hiddenIds);
      });

      test("should load all the nodes into the graph", () => {
        expect(graph.nodes()).toEqual([
          "SIMPLE-HEAD",
          "SIMPLE-CHILD",
          "SIMPLE-TAIL",
        ]);
      });

      test("should load all the edges into the graph", () => {
        expect(graph.edges()).toEqual([
          {
            name: "SIMPLE-HEAD-SIMPLE-CHILD",
            v: "SIMPLE-HEAD",
            w: "SIMPLE-CHILD",
          },
          {
            name: "SIMPLE-CHILD-SIMPLE-TAIL",
            v: "SIMPLE-CHILD",
            w: "SIMPLE-TAIL",
          },
        ]);
      });
    });

    describe("multiple graphs build", () => {
      const hiddenIds: Set<NodeId> = new Set();
      const graphs = [testGraphs["SIMPLE"], testGraphs["SIMPLE-MULT-OUT"]];
      let graph: GraphLib;

      beforeEach(() => {
        graph = buildGraph(graphs, hiddenIds);
      });

      test("should load all the nodes into the graph", () => {
        expect(graph.nodes()).toEqual([
          "SIMPLE-HEAD",
          "SIMPLE-CHILD",
          "SIMPLE-TAIL",
          "SIMPLE-TAIL-ONE",
          "SIMPLE-TAIL-TWO",
        ]);
      });

      test("should load all the edges into the graph", () => {
        expect(graph.edges()).toEqual([
          {
            name: "SIMPLE-HEAD-SIMPLE-CHILD",
            v: "SIMPLE-HEAD",
            w: "SIMPLE-CHILD",
          },
          {
            name: "SIMPLE-CHILD-SIMPLE-TAIL",
            v: "SIMPLE-CHILD",
            w: "SIMPLE-TAIL",
          },
          {
            name: "SIMPLE-CHILD-SIMPLE-TAIL-ONE",
            v: "SIMPLE-CHILD",
            w: "SIMPLE-TAIL-ONE",
          },
          {
            name: "SIMPLE-CHILD-SIMPLE-TAIL-TWO",
            v: "SIMPLE-CHILD",
            w: "SIMPLE-TAIL-TWO",
          },
        ]);
      });

      test("should map common nodes to point to both parent graphs", () => {
        expect(
          graph
            .nodes()
            .map((id) => graph.node(id))
            .map(({ data }) => data)
        ).toEqual([
          {
            id: "SIMPLE-HEAD",
            graphIds: ["SIMPLE", "SIMPLE-MULT-OUT"],
            isParent: false,
          },
          {
            id: "SIMPLE-CHILD",
            graphIds: ["SIMPLE", "SIMPLE-MULT-OUT"],
            isParent: false,
          },
          {
            id: "SIMPLE-TAIL",
            graphIds: ["SIMPLE"],
            isParent: false,
          },
          {
            id: "SIMPLE-TAIL-ONE",
            graphIds: ["SIMPLE-MULT-OUT"],
            isParent: false,
          },
          {
            id: "SIMPLE-TAIL-TWO",
            graphIds: ["SIMPLE-MULT-OUT"],
            isParent: false,
          },
        ]);
      });

      test("should map common edges to point to both parent graphs", () => {
        expect(
          graph
            .edges()
            .map(({ v, w, name }) => graph.edge(v, w, name))
            .map(({ data }) => data)
        ).toEqual([
          {
            id: "SIMPLE-HEAD-SIMPLE-CHILD",
            graphIds: ["SIMPLE", "SIMPLE-MULT-OUT"],
            source: "SIMPLE-HEAD",
            target: "SIMPLE-CHILD",
          },
          {
            id: "SIMPLE-CHILD-SIMPLE-TAIL",
            graphIds: ["SIMPLE"],
            source: "SIMPLE-CHILD",
            target: "SIMPLE-TAIL",
          },
          {
            id: "SIMPLE-CHILD-SIMPLE-TAIL-ONE",
            graphIds: ["SIMPLE-MULT-OUT"],
            source: "SIMPLE-CHILD",
            target: "SIMPLE-TAIL-ONE",
          },
          {
            id: "SIMPLE-CHILD-SIMPLE-TAIL-TWO",
            graphIds: ["SIMPLE-MULT-OUT"],
            source: "SIMPLE-CHILD",
            target: "SIMPLE-TAIL-TWO",
          },
        ]);
      });
    });

    describe("single graph build with hidden nodes", () => {
      const hiddenIds: Set<NodeId> = new Set(["SIMPLE-CHILD"]);
      const graphs = [testGraphs["SIMPLE"]];
      let graph: GraphLib;

      beforeEach(() => {
        graph = buildGraph(graphs, hiddenIds);
      });

      test("should mark the hidden node as 'filtered'", () => {
        expect(graph.node("SIMPLE-CHILD").classes).toEqual(["filtered"]);
      });

      test("should add an edge spanning our hidden node", () => {
        expect(graph.edge("SIMPLE-HEAD", "SIMPLE-TAIL")).not.toBeNull();
      });

      test("should mark any edges that touch our hidden node as 'filtered'", () => {
        expect(
          graph.edge("SIMPLE-HEAD", "SIMPLE-CHILD", "SIMPLE-HEAD-SIMPLE-CHILD")
            .classes
        ).toEqual(["filtered"]);
        expect(
          graph.edge("SIMPLE-CHILD", "SIMPLE-TAIL", "SIMPLE-CHILD-SIMPLE-TAIL")
            .classes
        ).toEqual(["filtered"]);
      });
    });

    describe("multiple graphs with hidden nodes", () => {
      const hiddenIds: Set<NodeId> = new Set(["SIMPLE-CHILD"]);
      const graphs = [testGraphs["SIMPLE"], testGraphs["SIMPLE-MULT-OUT"]];
      let graph: GraphLib;

      beforeEach(() => {
        graph = buildGraph(graphs, hiddenIds);
      });

      test("should load all the nodes into the graph", () => {
        expect(graph.nodes()).toEqual([
          "SIMPLE-HEAD",
          "SIMPLE-CHILD",
          "SIMPLE-TAIL",
          "SIMPLE-TAIL-ONE",
          "SIMPLE-TAIL-TWO",
        ]);
      });

      test("should mark our hidden node as 'filtered'", () => {
        expect(graph.node("SIMPLE-CHILD").classes).toEqual(["filtered"]);
      });

      test("should load all the edges into the graph", () => {
        expect(graph.edges()).toEqual([
          {
            name: "SIMPLE-HEAD-SIMPLE-CHILD",
            v: "SIMPLE-HEAD",
            w: "SIMPLE-CHILD",
          },
          {
            name: "SIMPLE-CHILD-SIMPLE-TAIL",
            v: "SIMPLE-CHILD",
            w: "SIMPLE-TAIL",
          },
          {
            name: "SIMPLE-CHILD-SIMPLE-TAIL-ONE",
            v: "SIMPLE-CHILD",
            w: "SIMPLE-TAIL-ONE",
          },
          {
            name: "SIMPLE-CHILD-SIMPLE-TAIL-TWO",
            v: "SIMPLE-CHILD",
            w: "SIMPLE-TAIL-TWO",
          },
          {
            name: "SIMPLE-HEAD\u200BSIMPLE-TAIL",
            v: "SIMPLE-HEAD",
            w: "SIMPLE-TAIL",
          },
          {
            name: "SIMPLE-HEAD\u200BSIMPLE-TAIL-ONE",
            v: "SIMPLE-HEAD",
            w: "SIMPLE-TAIL-ONE",
          },
          {
            name: "SIMPLE-HEAD\u200BSIMPLE-TAIL-TWO",
            v: "SIMPLE-HEAD",
            w: "SIMPLE-TAIL-TWO",
          },
        ]);
      });

      test("should mark all edges touching our hidden node as 'filtered'", () => {
        expect(
          graph.edge("SIMPLE-HEAD", "SIMPLE-CHILD", "SIMPLE-HEAD-SIMPLE-CHILD")
            .classes
        ).toEqual(["filtered"]);
        expect(
          graph.edge("SIMPLE-CHILD", "SIMPLE-TAIL", "SIMPLE-CHILD-SIMPLE-TAIL")
            .classes
        ).toEqual(["filtered"]);
        expect(
          graph.edge(
            "SIMPLE-CHILD",
            "SIMPLE-TAIL-ONE",
            "SIMPLE-CHILD-SIMPLE-TAIL-ONE"
          ).classes
        ).toEqual(["filtered"]);
        expect(
          graph.edge(
            "SIMPLE-CHILD",
            "SIMPLE-TAIL-TWO",
            "SIMPLE-CHILD-SIMPLE-TAIL-TWO"
          ).classes
        ).toEqual(["filtered"]);
      });

      test("should map common nodes to point to both parent graphs", () => {
        expect(
          graph
            .nodes()
            .map((id) => graph.node(id))
            .map(({ data }) => data)
        ).toEqual([
          {
            id: "SIMPLE-HEAD",
            graphIds: ["SIMPLE", "SIMPLE-MULT-OUT"],
            isParent: false,
          },
          {
            id: "SIMPLE-CHILD",
            graphIds: ["SIMPLE", "SIMPLE-MULT-OUT"],
            isParent: false,
          },
          {
            id: "SIMPLE-TAIL",
            graphIds: ["SIMPLE"],
            isParent: false,
          },
          {
            id: "SIMPLE-TAIL-ONE",
            graphIds: ["SIMPLE-MULT-OUT"],
            isParent: false,
          },
          {
            id: "SIMPLE-TAIL-TWO",
            graphIds: ["SIMPLE-MULT-OUT"],
            isParent: false,
          },
        ]);
      });

      test("should mark hidden node as 'filtered'", () => {
        expect(graph.node("SIMPLE-CHILD").classes).toEqual(["filtered"]);
      });

      test("should map common edges to point to both parent graphs", () => {
        expect(
          graph
            .edges()
            .filter(({ v, w }) => !hiddenIds.has(v) && !hiddenIds.has(w))
            .map(({ v, w, name }) => graph.edge(v, w, name))
            .map(({ data }) => data)
        ).toEqual([
          {
            id: "SIMPLE-HEAD​SIMPLE-TAIL",
            graphIds: ["SIMPLE"],
            source: "SIMPLE-HEAD",
            target: "SIMPLE-TAIL",
          },
          {
            id: "SIMPLE-HEAD​SIMPLE-TAIL-ONE",
            graphIds: ["SIMPLE-MULT-OUT"],
            source: "SIMPLE-HEAD",
            target: "SIMPLE-TAIL-ONE",
          },
          {
            id: "SIMPLE-HEAD​SIMPLE-TAIL-TWO",
            graphIds: ["SIMPLE-MULT-OUT"],
            source: "SIMPLE-HEAD",
            target: "SIMPLE-TAIL-TWO",
          },
        ]);
      });
    });

    describe("graph is parent/child", () => {
      const hiddenIds: Set<NodeId> = new Set();
      const graphs = [testGraphs["HAS-CHILDREN"]];
      let graph: GraphLib;

      beforeEach(() => {
        graph = buildGraph(graphs, hiddenIds);
      });

      test("should load all the nodes", () => {
        expect(graph.nodes()).toEqual([
          "HC-HEAD",
          "HC-PARENT",
          "HC-CHILD",
          "HC-TAIL",
        ]);
      });

      test("should load all the edges into the graph", () => {
        expect(graph.edges()).toEqual([
          { name: "HC-HEAD-HC-CHILD", v: "HC-HEAD", w: "HC-CHILD" },
          { name: "HC-CHILD-HC-TAIL", v: "HC-CHILD", w: "HC-TAIL" },
        ]);
      });
    });

    describe("with hidden node", () => {
      describe("when given a graph and a valid hidden node", () => {
        const hiddenIds: Set<NodeId> = new Set(["SIMPLE-CHILD"]);
        const graphs = [testGraphs["SIMPLE"]];
        let graph: GraphLib;

        beforeEach(() => {
          graph = buildGraph(graphs, hiddenIds);
        });

        test("it should mark the hidden node as 'filtered", () => {
          expect(graph.node("SIMPLE-CHILD").classes).toEqual(["filtered"]);
        });

        test("it should remove the edges to/from the hidden node from the graph", () => {
          expect(graph.edges()).not.toContain([
            {
              name: "SIMPLE-HEAD-SIMPLE-CHILD",
              v: "SIMPLE-HEAD",
              w: "SIMPLE-CHILD",
            },
            {
              name: "SIMPLE-CHILD-SIMPLE-TAIL",
              v: "SIMPLE-CHILD",
              w: "SIMPLE-TAIL",
            },
          ]);
        });

        test("it should add edge to map the hidden node", () => {
          expect(
            graph
              .edges()
              .filter(
                ({ v, w, name }) =>
                  graph.edge(v, w, name).classes?.[0] !== "filtered"
              )
          ).toEqual([
            {
              name: "SIMPLE-HEAD\u200BSIMPLE-TAIL",
              v: "SIMPLE-HEAD",
              w: "SIMPLE-TAIL",
            },
          ]);
        });
      });

      describe("when given a graph with and an invalid hidden node", () => {
        const hiddenIds: Set<NodeId> = new Set(["INVALID"]);
        const graphs = [testGraphs["SIMPLE"]];
        let graph: GraphLib;

        beforeEach(() => {
          graph = buildGraph(graphs, hiddenIds);
        });

        test("should still load all the nodes into the graph", () => {
          expect(graph.nodes()).toEqual([
            "SIMPLE-HEAD",
            "SIMPLE-CHILD",
            "SIMPLE-TAIL",
          ]);
        });
      });
    });
  });
});

import React, {
  useCallback,
  useEffect,
  useState,
  MouseEvent,
  ReactElement,
  ReactNode,
} from "react";
import {
  BiArrowToLeft,
  BiArrowToRight,
  BiDotsHorizontalRounded,
} from "react-icons/bi";

import "../styles/PanelGrid.scss";

enum ResizeId {
  NONE,
  RIGHT_SIDEBAR,
  BODY,
}

interface Dimensions {
  width: number;
  height: number;
}

export interface PanelDimensions {
  graphWindow: Dimensions;
  cardWindow: Dimensions;
  rightSidebar: Dimensions;
}

interface PanelGridProps {
  children: [
    ReactElement<typeof GraphWindow>,
    ReactElement<typeof CardWindow>,
    ReactElement<typeof RightSidebar>
  ];
  onResize: (dim: PanelDimensions) => void;
  onDragStart: () => void;
  onDragEnd: () => void;
}

interface PanelGridComposition {
  RightSidebar: React.FC<RightSidebarProps>;
  GraphWindow: React.FC<GraphWindowProps>;
  CardWindow: React.FC<CardWindowProps>;
}

const SIDEBAR_HANDLE_WIDTH = 24;
const SIDEBAR_DEFAULT_WIDTH = 450;
const GRAPH_WINDOW_DEFAULT_HEIGHT = 500;

export const PanelGrid: React.FC<PanelGridProps> & PanelGridComposition = ({
  children,
  onDragEnd,
  onDragStart,
  onResize,
}) => {
  const [isResizing, setIsResizing] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [resizeId, setResizeId] = useState(ResizeId.NONE);
  const [graphWindowHeight, setGraphWindowHeight] = useState(
    GRAPH_WINDOW_DEFAULT_HEIGHT
  );
  const [rightSidebarWidth, setRightSidebarWidth] = useState(
    SIDEBAR_DEFAULT_WIDTH
  );

  useEffect(() => {
    onResize({
      graphWindow: { width: 0, height: graphWindowHeight },
      cardWindow: { width: 0, height: 0 },
      rightSidebar: { width: rightSidebarWidth, height: 0 },
    });
  }, [graphWindowHeight, onResize, rightSidebarWidth]);

  const toggleSidebar = useCallback(() => {
    isSidebarOpen
      ? setRightSidebarWidth(SIDEBAR_HANDLE_WIDTH)
      : setRightSidebarWidth(SIDEBAR_DEFAULT_WIDTH);

    setIsSidebarOpen(!isSidebarOpen);
  }, [isSidebarOpen, setRightSidebarWidth]);

  const lockPageSectionSizes = useCallback(() => {
    setIsResizing(false);
    setResizeId((prevId) => {
      if (prevId === ResizeId.BODY) {
        onDragEnd();
      }
      return ResizeId.NONE;
    });
  }, [onDragEnd]);

  const initVerticalResizing = useCallback(() => {
    setIsResizing(true);
    setResizeId(ResizeId.BODY);
    onDragStart();
  }, [onDragStart, setIsResizing, setResizeId]);

  const adjustPageSectionSizes = useCallback(
    (e: MouseEvent<HTMLDivElement, globalThis.MouseEvent>) => {
      if (isResizing) {
        switch (resizeId) {
          case ResizeId.RIGHT_SIDEBAR:
            setRightSidebarWidth(document.body.clientWidth - e.clientX);
            break;
          case ResizeId.BODY:
            setGraphWindowHeight(e.clientY);
            break;
          default:
            console.error(`UNKNOWN resizeId(${resizeId})`);
        }
      }
    },
    [isResizing, resizeId, setRightSidebarWidth, setGraphWindowHeight]
  );

  return (
    <div
      className="PanelGrid"
      onMouseMove={adjustPageSectionSizes}
      onMouseUp={lockPageSectionSizes}
    >
      <div
        className="body"
        style={{
          width: `calc(100vw - ${rightSidebarWidth}px)`,
        }}
      >
        <div
          className="graphWindow border-bottom"
          style={{ height: `${graphWindowHeight}px` }}
        >
          <div className="bodyContent">{children[0]}</div>
          <div className="verticalHandleBox">
            <div className="verticalHandle" onMouseDown={initVerticalResizing}>
              <BiDotsHorizontalRounded />
            </div>
          </div>
        </div>
        <div
          className="graphCardWindow d-flex flex-wrap"
          style={{ height: `calc(100vh - ${graphWindowHeight})` }}
        >
          {children[1]}
        </div>
      </div>
      <div
        className="rightSidebar border"
        style={{ width: `${rightSidebarWidth}px` }}
      >
        <div className="handleBox">
          <div className="handle" onMouseDown={toggleSidebar}>
            {isSidebarOpen ? (
              <BiArrowToRight size="1.5em" />
            ) : (
              <BiArrowToLeft size="1.5em" />
            )}
          </div>
        </div>
        <div className="sidebarContent">{children[2]}</div>
      </div>
    </div>
  );
};

interface RightSidebarProps {
  children: ReactNode;
}

const RightSidebar: React.FC<RightSidebarProps> = ({ children }) => {
  return <>{children}</>;
};

PanelGrid.RightSidebar = RightSidebar;

interface GraphWindowProps {
  children: ReactNode;
}

const GraphWindow: React.FC<GraphWindowProps> = ({ children }) => {
  return <>{children}</>;
};

PanelGrid.GraphWindow = GraphWindow;

interface CardWindowProps {
  children: ReactNode;
}

const CardWindow: React.FC<CardWindowProps> = ({ children }) => {
  return <>{children}</>;
};

PanelGrid.CardWindow = CardWindow;

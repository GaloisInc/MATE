import React from "react";
import { BiHourglass } from "react-icons/bi";

interface ProcessingIndicatorProps {
  isProcessing: boolean;
}

export const ProcessingIndicator: React.FC<ProcessingIndicatorProps> = ({
  isProcessing,
}) => {
  return isProcessing ? (
    <BiHourglass
      className="ProcessingIndicator m-2"
      size="1.25em"
      title="processing graph"
    />
  ) : null;
};

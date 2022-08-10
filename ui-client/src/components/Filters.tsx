import React, { useCallback, useEffect, useState } from "react";

import { Card } from "react-bootstrap";

import { ToggleSwitch } from "./ToggleSwitch";

import "../styles/Filters.scss";

export type FilterChoice = string;

interface FiltersProps {
  initialChoices: FilterChoice[];
  onSelect: (filterChoices: FilterChoice[]) => void;
}

export const Filters: React.FC<FiltersProps> = ({
  initialChoices = [],
  onSelect,
}) => {
  const [filterChoices, setFilterChoices] =
    useState<FilterChoice[]>(initialChoices);

  useEffect(() => {
    setFilterChoices(initialChoices);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialChoices.length]);

  const onMemoryFilterChange = useCallback(
    () =>
      setFilterChoices((choices) => {
        const newFilters = choices.includes("MemoryLocation")
          ? choices.filter((c) => c !== "MemoryLocation")
          : choices.concat("MemoryLocation");

        onSelect(newFilters);

        return newFilters;
      }),
    [onSelect]
  );

  return (
    <Card className="Filters">
      <Card.Header>Hide Nodes</Card.Header>
      <Card.Body className="p-2">
        <ToggleSwitch
          id="memory-filter"
          label="memory"
          onToggle={onMemoryFilterChange}
          checked={
            filterChoices.find((f) => f === "MemoryLocation") !== undefined
          }
        />
      </Card.Body>
    </Card>
  );
};

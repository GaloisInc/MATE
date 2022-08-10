import React, { useCallback, useEffect, useState } from "react";

import "../styles/ToggleSwitch.scss";

interface ToggleSwitchProps {
  id: string;
  label: string;
  onToggle: () => void;
  checked?: boolean;
  inline?: boolean;
}

export const ToggleSwitch: React.FC<ToggleSwitchProps> = ({
  checked = false,
  id,
  inline = false,
  label,
  onToggle,
}) => {
  const [isChecked, setIsChecked] = useState(checked);

  useEffect(() => setIsChecked(checked), [checked]);

  const handleClick = useCallback(() => {
    setIsChecked((prev) => !prev);
    onToggle();
  }, [onToggle]);

  return (
    <div className={`ToggleSwitch ${inline ? "inline" : ""}`}>
      <input
        type="checkbox"
        id={id}
        className="checkbox"
        onChange={handleClick}
        checked={isChecked}
      />
      <label htmlFor={id} className="switch" />
      <div className="caption">{label}</div>
    </div>
  );
};

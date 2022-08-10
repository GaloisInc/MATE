import { Alert } from "react-bootstrap";

interface WarningsProps {
  warnings: string[];
}

export const Warnings = ({ warnings }: WarningsProps) =>
  warnings.length > 0 ? (
    <Alert variant="warning" className="pb-1">
      Manticore encountered the following issues doing this analysis:
      <ul className="mt-1">
        {warnings.map((w) => (
          <li key={`warning-${w}`}>{w}</li>
        ))}
      </ul>
    </Alert>
  ) : null;

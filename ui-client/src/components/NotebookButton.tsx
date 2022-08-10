import { useCallback, useState } from "react";
import { Button, Spinner } from "react-bootstrap";

import { createNotebook, getNotebook } from "../lib/api";

const DEFAULT_LABEL = "Open Jupyter Notebook";

const makeNotebookName = (buildId: string, binaryName: string) =>
  `${binaryName}-${buildId}.ipynb`;
const makeNotebookUrl = (domain: string, notebookName: string) =>
  `http://${domain}:8889/notebooks/${notebookName}`;

interface NotebookButtonProps {
  binaryName?: string;
  buildId: string;
  size?: "sm" | "lg";
}

export const NotebookButton = ({
  binaryName,
  buildId,
  size,
}: NotebookButtonProps) => {
  const [isLoading, setIsLoading] = useState(false);
  const [label, setLabel] = useState(DEFAULT_LABEL);

  const handleNotebookClick = useCallback(() => {
    if (binaryName) {
      const notebookName = makeNotebookName(buildId, binaryName);
      setIsLoading(true);
      setLabel("Looking up notebook..");
      getNotebook(notebookName)
        .then((notebook) => {
          const url = makeNotebookUrl(window.location.hostname, notebookName);

          if (notebook === null) {
            setLabel("Creating notebook..");
            createNotebook(notebookName, buildId).then(() => {
              window.open(url, notebookName);
            });
          } else {
            window.open(url, notebookName);
          }
        })
        .finally(() => {
          setIsLoading(false);
          setLabel(DEFAULT_LABEL);
        });
    }
  }, [binaryName, buildId]);

  return (
    <Button
      onClick={() => handleNotebookClick()}
      disabled={!binaryName}
      className="NotebookButton"
      size={size}
    >
      {isLoading ? (
        <Spinner
          as="span"
          animation="grow"
          size="sm"
          role="status"
          aria-hidden={true}
        />
      ) : (
        ""
      )}
      {label}
    </Button>
  );
};

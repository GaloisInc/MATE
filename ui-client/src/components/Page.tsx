import React, { ReactNode } from "react";
import { Container } from "react-bootstrap";

import { Header } from "./Header";
import { LoadingIndicator } from "./LoadingIndicator";

import "../styles/Page.scss";

type PageProps = {
  children: ReactNode;
  className?: string;
  isLoading?: boolean;
  loadingMessage?: string;
  buildId?: string;
  binaryName?: string;
};

export const Page: React.FC<PageProps> = ({
  children,
  className = "",
  isLoading,
  loadingMessage,
  buildId,
  binaryName,
}) => {
  return (
    <Container className={`Page m0 ${className}`} fluid>
      <Header buildId={buildId} binaryName={binaryName} />
      {isLoading && <LoadingIndicator message={loadingMessage} />}
      {children}
    </Container>
  );
};

import { useState } from "react";

interface UsePageHookParams {
  message?: string;
}

export const usePage = ({ message }: UsePageHookParams = {}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState(message ?? "Loading...");

  return { isLoading, loadingMessage, setIsLoading, setLoadingMessage };
};

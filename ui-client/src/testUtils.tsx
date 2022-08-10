import type { ReactChildren } from "react";
import { QueryClient, QueryClientProvider, setLogger } from "react-query";

setLogger({
  log: console.log,
  warn: console.warn,
  // ✅ no more errors on the console
  error: () => {},
});

export const createQueryWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return ({ children }: { children: ReactChildren }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

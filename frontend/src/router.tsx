import { QueryCache, QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { toast } from "sonner";
import { routeTree } from "./routeTree.gen";

const TOAST_THROTTLE_MS = 30_000;
let lastErrorToast = 0;

function toastQueryError(error: unknown) {
  const now = Date.now();
  if (now - lastErrorToast > TOAST_THROTTLE_MS) {
    lastErrorToast = now;
    const message = error instanceof Error ? error.message : String(error);
    if (/failed to fetch|networkerror|load failed/i.test(message)) {
      toast.error("Backend not reachable", {
        description: 'Start both servers with "python run_all.py" from the repo root.',
      });
    } else {
      toast.error("Request failed", { description: message });
    }
  }
}

export const getRouter = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: 2, refetchOnWindowFocus: false } },
    queryCache: new QueryCache({ onError: toastQueryError }),
  });

  const router = createRouter({
    routeTree,
    context: { queryClient },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  });

  return router;
};

import { createContext, useContext, useState, type ReactNode } from "react";
import type { Mode } from "./types";

const Ctx = createContext<{ mode: Mode; setMode: (m: Mode) => void; runId: string | null; setRunId: (id: string | null) => void } | null>(null);

export function OpsProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>("simulation");
  const [runId, setRunId] = useState<string | null>(null);
  return <Ctx.Provider value={{ mode, setMode, runId, setRunId }}>{children}</Ctx.Provider>;
}
export function useOps() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useOps outside provider");
  return c;
}

"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type HarnessContextValue = {
  open: boolean;
  openHarness: () => void;
  closeHarness: () => void;
};

const HarnessContext = createContext<HarnessContextValue | null>(null);

export function HarnessProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const openHarness = useCallback(() => setOpen(true), []);
  const closeHarness = useCallback(() => setOpen(false), []);
  const value = useMemo(
    () => ({ open, openHarness, closeHarness }),
    [open, openHarness, closeHarness],
  );
  return <HarnessContext.Provider value={value}>{children}</HarnessContext.Provider>;
}

export function useHarness() {
  const value = useContext(HarnessContext);
  if (!value) throw new Error("useHarness must be used within HarnessProvider");
  return value;
}

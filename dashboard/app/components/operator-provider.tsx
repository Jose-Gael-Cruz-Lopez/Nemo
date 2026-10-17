"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
type OperatorAccess = { token: string; connect: (candidate: string, signal?: AbortSignal) => Promise<void>; disconnect: () => void };
const OperatorContext = createContext<OperatorAccess | null>(null);

// The existing local operator credential lives only in this tab's React tree.
// It is never put in URLs, browser storage, cookies, or rendered markup.
export function OperatorProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState("");
  const generation = useRef(0);
  const disconnect = useCallback(() => { ++generation.current; setToken(""); }, []);
  const connect = useCallback(async (candidate: string, signal?: AbortSignal) => {
    const run = ++generation.current;
    const value = candidate.trim();
    if (!value) throw new Error("Enter your local operator token.");
    let response: Response;
    try {
      response = await fetch(`${API}/api/v1/operator/session`, {
        headers: { Authorization: `Bearer ${value}` }, cache: "no-store",
        signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(8000)]) : AbortSignal.timeout(8000),
      });
    } catch {
      signal?.throwIfAborted();
      throw new Error("The local API could not be reached. Start ReefTrace, then try again.");
    }
    if (response.status === 401) throw new Error("That token was not accepted. Check your local ReefTrace .env file.");
    if (response.status === 503) throw new Error("Operator access is not configured on the local API.");
    if (!response.ok) throw new Error(`Operator verification failed (${response.status}). Try again after checking the API.`);
    const result = await response.json() as { authenticated?: boolean; scope?: string };
    if (result.authenticated !== true || result.scope !== "local_operator") throw new Error("The API did not confirm operator access.");
    signal?.throwIfAborted();
    if (run !== generation.current) throw new Error("This sign-in was superseded. Try again if you still need operator access.");
    setToken(value);
  }, []);
  return <OperatorContext.Provider value={{ token, connect, disconnect }}>{children}</OperatorContext.Provider>;
}

export function useOperator() {
  const access = useContext(OperatorContext);
  if (!access) throw new Error("Operator access requires OperatorProvider.");
  return access;
}

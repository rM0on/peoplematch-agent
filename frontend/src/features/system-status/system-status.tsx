"use client";

import { useEffect, useState } from "react";

import { fetchBackendHealth } from "@/lib/api";
import type { HealthData } from "@/types/api";


type StatusState =
  | { kind: "loading" }
  | { kind: "healthy"; data: HealthData; requestId: string }
  | { kind: "unavailable" };


export function SystemStatus() {
  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState<StatusState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    fetchBackendHealth(controller.signal)
      .then((response) => {
        if (!response.success || !response.data) {
          throw new Error("Backend returned an unsuccessful health response");
        }
        if (active) {
          setStatus({
            kind: "healthy",
            data: response.data,
            requestId: response.request_id,
          });
        }
      })
      .catch(() => {
        if (active) {
          setStatus({ kind: "unavailable" });
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [attempt]);

  const isHealthy = status.kind === "healthy";

  return (
    <section
      aria-labelledby="backend-status-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.07)]"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            Live integration
          </p>
          <h2
            id="backend-status-title"
            className="mt-2 text-xl font-semibold tracking-tight text-slate-950"
          >
            Backend status
          </h2>
        </div>
        <span
          aria-hidden="true"
          className={`mt-1 h-3 w-3 rounded-full ${
            status.kind === "loading"
              ? "animate-pulse bg-amber-400"
              : isHealthy
                ? "bg-emerald-500"
                : "bg-rose-500"
          }`}
        />
      </div>

      <div className="mt-8 min-h-24" aria-live="polite" aria-atomic="true">
        {status.kind === "loading" && (
          <div>
            <p className="text-2xl font-semibold text-slate-900">Checking…</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Requesting the FastAPI liveness endpoint.
            </p>
          </div>
        )}

        {status.kind === "healthy" && (
          <div>
            <p className="text-2xl font-semibold text-emerald-700">Healthy</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {status.data.service} · v{status.data.version} · {status.data.environment}
            </p>
            <p className="mt-3 truncate font-mono text-xs text-slate-400">
              Request {status.requestId}
            </p>
          </div>
        )}

        {status.kind === "unavailable" && (
          <div>
            <p className="text-2xl font-semibold text-rose-700">Unavailable</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              The backend did not return a valid health response.
            </p>
            <button
              type="button"
              onClick={() => {
                setStatus({ kind: "loading" });
                setAttempt((current) => current + 1);
              }}
              className="mt-4 rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-800 transition hover:border-slate-900 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
            >
              Retry check
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

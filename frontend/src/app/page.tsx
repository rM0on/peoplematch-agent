import { ModuleCard } from "@/components/module-card";
import { SystemStatus } from "@/features/system-status/system-status";


const plannedModules = [
  {
    title: "Candidate Profiles",
    description: "Structured skills, direction, constraints, and project evidence.",
    phase: "Phase 1–2",
  },
  {
    title: "Job Profiles",
    description: "Role requirements modeled separately from raw job-description text.",
    phase: "Phase 1–2",
  },
  {
    title: "Matching Engine",
    description: "Retrieval, feature scoring, ranking, and reranking with traceable steps.",
    phase: "Phase 4–7",
  },
  {
    title: "Agent Workflow",
    description: "Orchestration boundaries for repeatable, inspectable match runs.",
    phase: "Phase 8",
  },
  {
    title: "Bad Case Review",
    description: "Failure attribution that separates ranking evidence from explanation.",
    phase: "Phase 10",
  },
  {
    title: "Offline Evaluation",
    description: "Sandbox datasets and documented comparisons before algorithm claims.",
    phase: "Phase 11",
  },
] as const;


export default function Home() {
  return (
    <main className="min-h-screen overflow-hidden bg-slate-50 text-slate-950">
      <div aria-hidden="true" className="page-glow" />

      <header className="relative mx-auto flex max-w-7xl items-center justify-between px-6 py-7 lg:px-10">
        <a
          href="#overview"
          className="text-sm font-bold tracking-tight text-slate-950 focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-slate-900"
        >
          PeopleMatch Agent
        </a>
        <span className="rounded-full border border-slate-200 bg-white/80 px-4 py-2 text-xs font-semibold text-slate-600 backdrop-blur">
          Local prototype
        </span>
      </header>

      <section
        id="overview"
        aria-labelledby="page-title"
        className="relative mx-auto grid max-w-7xl gap-12 px-6 pb-24 pt-16 lg:grid-cols-[minmax(0,1.45fr)_minmax(300px,0.55fr)] lg:items-end lg:px-10 lg:pb-32 lg:pt-24"
      >
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-indigo-700">
            Phase 0 · Engineering Bootstrap
          </p>
          <h1
            id="page-title"
            className="mt-6 max-w-4xl text-5xl font-semibold leading-[1.02] tracking-[-0.045em] text-slate-950 sm:text-6xl lg:text-7xl"
          >
            Evidence-aware AI Builder matching &amp; recommendation system
          </h1>
          <p className="mt-8 max-w-2xl text-lg leading-8 text-slate-600">
            A local engineering foundation for matching people and AI roles with
            explicit evidence, traceable ranking, grounded explanations, and
            evaluation-first iteration.
          </p>
        </div>

        <SystemStatus />
      </section>

      <section
        aria-labelledby="modules-title"
        className="relative border-t border-slate-200/80 bg-white/55"
      >
        <div className="mx-auto max-w-7xl px-6 py-20 lg:px-10 lg:py-28">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
              Product boundaries
            </p>
            <h2
              id="modules-title"
              className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl"
            >
              Planned modules, not simulated features
            </h2>
            <p className="mt-5 text-base leading-7 text-slate-600">
              Phase 0 establishes the interfaces and documentation these modules
              will grow into. No recommendation data or performance metrics are
              fabricated here.
            </p>
          </div>

          <div className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {plannedModules.map((module) => (
              <ModuleCard key={module.title} {...module} />
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-slate-950 text-slate-300">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-8 text-sm sm:flex-row sm:items-center sm:justify-between lg:px-10">
          <p>Phase 0 — Product Definition &amp; Engineering Bootstrap</p>
          <p className="text-slate-500">Synthetic and sandbox data only.</p>
        </div>
      </footer>
    </main>
  );
}

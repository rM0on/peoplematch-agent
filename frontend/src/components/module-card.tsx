interface ModuleCardProps {
  title: string;
  description: string;
  phase: string;
}


export function ModuleCard({ title, description, phase }: ModuleCardProps) {
  return (
    <article className="group flex min-h-48 flex-col justify-between rounded-3xl border border-slate-200 bg-white p-6 transition duration-200 hover:-translate-y-1 hover:border-slate-300 hover:shadow-[0_18px_48px_rgba(15,23,42,0.08)]">
      <div>
        <div className="flex items-center justify-between gap-3">
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600">
            Planned
          </span>
          <span className="text-xs font-medium text-slate-400">{phase}</span>
        </div>
        <h3 className="mt-6 text-xl font-semibold tracking-tight text-slate-950">
          {title}
        </h3>
      </div>
      <p className="mt-5 text-sm leading-6 text-slate-600">{description}</p>
    </article>
  );
}

"use client";

type Props = {
  mapping: Record<string, string>;
};

export function FieldMappingEditor({ mapping }: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-900">Field mapping</h3>
      <div className="space-y-2">
        {Object.entries(mapping).map(([source, target]) => (
          <div
            key={`${source}-${target}`}
            className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
          >
            <span>{source}</span>
            <span className="text-slate-500">{target}</span>
          </div>
        ))}
        {Object.keys(mapping).length === 0 ? (
          <p className="text-sm text-slate-500">No mapping defined.</p>
        ) : null}
      </div>
    </div>
  );
}


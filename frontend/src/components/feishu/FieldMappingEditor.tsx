"use client";

import { useEffect, useState } from "react";

type MappingRow = {
  source: string;
  target: string;
};

type Props = {
  mapping: Record<string, string>;
  onSave?: (mapping: Record<string, string>) => Promise<void>;
  isSaving?: boolean;
};

function toRows(mapping: Record<string, string>): MappingRow[] {
  return Object.entries(mapping).map(([source, target]) => ({ source, target }));
}

export function FieldMappingEditor({ mapping, onSave, isSaving = false }: Props) {
  const [rows, setRows] = useState<MappingRow[]>(() => toRows(mapping));

  useEffect(() => {
    setRows(toRows(mapping));
  }, [mapping]);

  const hasRows = rows.length > 0;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">字段映射</h3>
          <p className="mt-1 text-xs text-slate-500">
            {hasRows ? `已配置 ${rows.length} 项` : "当前未配置映射"}
          </p>
        </div>
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
          onClick={() => {
            setRows((current) => [...current, { source: "", target: "" }]);
          }}
        >
          添加映射
        </button>
      </div>
      <div className="space-y-2">
        {rows.map((row, index) => (
          <div
            key={`${index}-${row.source}-${row.target}`}
            className="grid gap-2 rounded-lg bg-slate-50 px-3 py-3 md:grid-cols-[1fr_1fr_auto]"
          >
            <input
              className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-0"
              placeholder="飞书字段名"
              value={row.source}
              onChange={(event) => {
                const value = event.target.value;
                setRows((current) =>
                  current.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, source: value } : item,
                  ),
                );
              }}
            />
            <input
              className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-0"
              placeholder="Mission Control 字段名 (如: title, board, status)"
              value={row.target}
              onChange={(event) => {
                const value = event.target.value;
                setRows((current) =>
                  current.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, target: value } : item,
                  ),
                );
              }}
            />
            <button
              type="button"
              className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700"
              onClick={() => {
                setRows((current) => current.filter((_, itemIndex) => itemIndex !== index));
              }}
            >
              删除
            </button>
          </div>
        ))}
        {!hasRows ? (
          <p className="text-sm text-slate-500">还没有定义字段映射，默认只能同步最基础字段。</p>
        ) : null}
      </div>
      {onSave ? (
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            disabled={isSaving}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            onClick={async () => {
              const nextMapping = rows.reduce<Record<string, string>>((acc, row) => {
                const source = row.source.trim();
                const target = row.target.trim();
                if (!source || !target) {
                  return acc;
                }
                acc[source] = target;
                return acc;
              }, {});
              await onSave(nextMapping);
            }}
          >
            {isSaving ? "保存中..." : "保存字段映射"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

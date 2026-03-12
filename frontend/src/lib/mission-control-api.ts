"use client";

import { customFetch } from "@/api/mutator";

export async function apiGet<T>(path: string): Promise<T> {
  const res = await customFetch<{ data: T }>(path, { method: "GET", cache: "no-store" });
  return res.data;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await customFetch<{ data: T }>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  return res.data;
}

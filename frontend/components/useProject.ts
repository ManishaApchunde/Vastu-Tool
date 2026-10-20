"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/services/api";
import type { Project } from "@/types/api";

export function useProject(id: string) {
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<unknown>(null);
  const reload = useCallback(async () => {
    try {
      setProject(await api.project(id));
      setError(null);
    } catch (e) {
      setError(e);
    }
  }, [id]);
  useEffect(() => { reload(); }, [reload]);
  return { project, error, reload, setProject };
}

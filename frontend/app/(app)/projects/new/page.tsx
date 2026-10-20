"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ErrorNote, Spinner } from "@/components/ui";
import { api } from "@/services/api";

const TYPES = [
  ["apartment", "Apartment"], ["villa", "Villa"], ["independent_house", "Independent house"],
  ["plot", "Plot"], ["office", "Office"], ["other", "Other"],
] as const;

export default function NewProjectPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", client: "", address: "", property_type: "apartment", area: "", notes: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const p = await api.createProject({
        name: form.name.trim(),
        property: {
          name: form.name.trim(),
          client_name: form.client.trim() || null,
          address: form.address.trim() || null,
          property_type: form.property_type,
          built_up_area_sqft: form.area ? Number(form.area) : null,
          notes: form.notes.trim() || null,
        },
      });
      router.push(`/projects/${p.id}/upload`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <div className="max-w-xl">
      <h1 className="page-title">New project</h1>
      <p className="mt-1 text-slate">Describe the property. You'll upload its floor plan next.</p>
      <form onSubmit={submit} className="panel mt-6 space-y-4 p-6">
        <div>
          <label className="label" htmlFor="name">Project name</label>
          <input id="name" required maxLength={200} className="field" value={form.name} onChange={set("name")} placeholder="e.g. Kothrud 2BHK, Flat 402" />
        </div>
        <div>
          <label className="label" htmlFor="client">Customer name <span className="font-normal text-slate">(optional, shown on the report)</span></label>
          <input id="client" maxLength={200} className="field" value={form.client} onChange={set("client")} autoComplete="off" />
        </div>
        <div>
          <label className="label" htmlFor="address">Address <span className="font-normal text-slate">(optional)</span></label>
          <input id="address" className="field" value={form.address} onChange={set("address")} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label" htmlFor="type">Property type</label>
            <select id="type" className="field" value={form.property_type} onChange={set("property_type")}>
              {TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="area">Built-up area, sq ft <span className="font-normal text-slate">(optional)</span></label>
            <input id="area" type="number" min={1} className="field" value={form.area} onChange={set("area")} />
          </div>
        </div>
        <div>
          <label className="label" htmlFor="notes">Notes <span className="font-normal text-slate">(optional)</span></label>
          <textarea id="notes" rows={3} className="field" value={form.notes} onChange={set("notes")} />
        </div>
        <ErrorNote error={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-quiet" onClick={() => router.back()}>Cancel</button>
          <button className="btn-primary" disabled={busy || !form.name.trim()}>{busy && <Spinner />} Create and upload plan</button>
        </div>
      </form>
    </div>
  );
}

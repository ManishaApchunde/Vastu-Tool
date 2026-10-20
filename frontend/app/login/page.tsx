"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Mark } from "@/components/AppShell";
import { ErrorNote, Spinner } from "@/components/ui";
import { api, auth } from "@/services/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = mode === "login" ? await api.login(email, password) : await api.register(email, password, name || undefined);
      auth.set(res.access_token);
      router.replace("/dashboard");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-5">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-2 font-display text-xl text-ink"><Mark size={26} /> Vastu Plan Analyzer</div>
        <form onSubmit={submit} className="panel space-y-4 p-6">
          <h1 className="font-display text-2xl">{mode === "login" ? "Sign in" : "Create an account"}</h1>
          {mode === "register" && (
            <div>
              <label className="label" htmlFor="name">Full name</label>
              <input id="name" className="field" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
            </div>
          )}
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" type="email" required className="field" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </div>
          <div>
            <label className="label" htmlFor="password">Password</label>
            <input id="password" type="password" required minLength={mode === "register" ? 8 : 1} className="field"
              value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"} />
            {mode === "register" && <p className="mt-1 text-xs text-slate">At least 8 characters.</p>}
          </div>
          <ErrorNote error={error} />
          <button className="btn-primary w-full" disabled={busy}>
            {busy && <Spinner />} {mode === "login" ? "Sign in" : "Create account"}
          </button>
          <p className="text-center text-sm text-slate">
            {mode === "login" ? "New here? " : "Already have an account? "}
            <button type="button" className="text-ink underline" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
              {mode === "login" ? "Create an account" : "Sign in"}
            </button>
          </p>
        </form>
        <p className="mt-4 text-sm text-slate">
          Demo account: <button type="button" className="text-ink underline"
            onClick={() => { setMode("login"); setEmail("demo@example.com"); setPassword("demo12345"); }}>
            demo@example.com / demo12345</button>
        </p>
      </div>
    </div>
  );
}

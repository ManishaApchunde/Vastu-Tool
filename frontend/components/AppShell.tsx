"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, auth } from "@/services/api";
import type { User } from "@/types/api";
import { Loading } from "./ui";

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!auth.token) {
      router.replace("/login");
      return;
    }
    api.me().then(setUser).catch(() => router.replace("/login"));
  }, [router]);

  if (!user) return <Loading label="Checking your session" />;

  const nav = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/projects", label: "Projects" },
  ];
  return (
    <div className="min-h-screen">
      <header className="border-b border-hairline bg-white">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:gap-8 sm:px-5">
          <Link href="/dashboard" className="flex items-center gap-2 font-display text-lg text-ink">
            <Mark /> <span className="hidden sm:inline">Vastu Plan Analyzer</span>
          </Link>
          <nav className="flex gap-1 text-sm">
            {nav.map((n) => (
              <Link key={n.href} href={n.href}
                className={`rounded px-3 py-1.5 ${path.startsWith(n.href) ? "bg-paper text-ink" : "text-ink-soft hover:text-ink"}`}>
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm text-slate">
            <span className="hidden sm:inline">{user.email}</span>
            <button className="btn-quiet" onClick={() => { auth.clear(); router.replace("/login"); }}>Sign out</button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-5">{children}</main>
    </div>
  );
}

/** Compass rose mark: the brand is orientation. */
export function Mark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <rect x="2.5" y="2.5" width="19" height="19" fill="none" stroke="#16283A" strokeWidth="1.5" />
      <path d="M8.8 2.5v19M15.2 2.5v19M2.5 8.8h19M2.5 15.2h19" stroke="#16283A" strokeWidth=".6" opacity=".45" />
      <path d="M12 4.5l2 7.5-2-1-2 1z" fill="#9C6B1C" />
      <circle cx="12" cy="12" r="1.3" fill="#16283A" />
    </svg>
  );
}

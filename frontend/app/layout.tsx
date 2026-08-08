import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AgentSync — Agentes que negocian por ti",
  description:
    "Configura tu agente, déjalo negociar en el ecosistema y aprueba solo las decisiones sensibles. B2B y P2P, un solo motor.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>
        <header className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-[var(--border)] bg-[var(--surface)] px-6 py-3">
          <Link href="/" className="flex items-center gap-2.5 font-bold tracking-tight">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--accent)] text-sm font-extrabold text-white">
              AS
            </span>
            <span>AgentSync</span>
          </Link>
          <nav className="flex gap-4 text-sm text-[var(--muted)]">
            <Link href="/" className="transition-colors hover:text-[var(--foreground)]">
              Inicio
            </Link>
            <Link href="/setup" className="transition-colors hover:text-[var(--foreground)]">
              Configurar agente
            </Link>
            <Link href="/ecosistema" className="transition-colors hover:text-[var(--foreground)]">
              Ecosistema
            </Link>
            <Link href="/bandeja" className="transition-colors hover:text-[var(--foreground)]">
              Bandeja
            </Link>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-[1080px] flex-1 px-6 pb-12 pt-7">
          {children}
        </main>
        <footer className="border-t border-[var(--border)] px-6 py-4 text-center text-xs text-[var(--muted)]">
          AgentSync — demo MVP · entorno simulado · los agentes nunca cruzan un
          límite duro sin tu aprobación
        </footer>
      </body>
    </html>
  );
}

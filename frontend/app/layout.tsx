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
        <header className="appHeader">
          <Link href="/" className="brand">
            <span className="brandMark">AS</span>
            <span>AgentSync</span>
          </Link>
          <nav className="mainNav">
            <Link href="/">Inicio</Link>
            <Link href="/setup">Configurar agente</Link>
            <Link href="/ecosistema">Ecosistema</Link>
          </nav>
        </header>
        <main className="appMain">{children}</main>
        <footer className="appFooter">
          AgentSync — demo MVP · entorno simulado · los agentes nunca cruzan un
          límite duro sin tu aprobación
        </footer>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { Quantico, Ubuntu } from "next/font/google";
import { AppShell } from "@/components/AppShell";
import { AgentSyncProvider } from "@/lib/store";
import "./globals.css";

const ubuntu = Ubuntu({
  variable: "--font-ubuntu",
  subsets: ["latin"],
  weight: ["300", "400", "500", "700"],
});

const quantico = Quantico({
  variable: "--font-quantico",
  subsets: ["latin"],
  weight: ["400", "700"],
});

export const metadata: Metadata = {
  title: "AgentSync — Agentes que negocian por ti",
  description:
    "Configura tu agente, déjalo negociar en el ecosistema y aprueba solo las decisiones sensibles. B2B y P2P, un solo motor.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className={`${ubuntu.variable} ${quantico.variable}`}>
      <body>
        <AgentSyncProvider>
          <AppShell>{children}</AppShell>
        </AgentSyncProvider>
      </body>
    </html>
  );
}

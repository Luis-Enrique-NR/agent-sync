import type { Metadata } from "next";
import { Quantico, Ubuntu } from "next/font/google";
import { AppShell } from "@/components/AppShell";
import { AuthProvider } from "@/lib/auth";
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
  title: "AgentSync — Un objetivo, varias negociaciones",
  description:
    "Define tu objetivo y tus límites. AgentSync encuentra oportunidades, negocia en paralelo y te consulta solo cuando una decisión importa.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className={`${ubuntu.variable} ${quantico.variable}`}>
      <body>
        <AgentSyncProvider>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </AgentSyncProvider>
      </body>
    </html>
  );
}

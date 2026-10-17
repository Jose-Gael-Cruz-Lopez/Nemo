import type { Metadata } from "next";
import "./globals.css";
import { OperatorProvider } from "./components/operator-provider";

export const metadata: Metadata = {
  title: "Reeftrace | Source intelligence",
  description: "Trace floating pollution. Compare interventions. Protect what matters.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><OperatorProvider>{children}</OperatorProvider></body>
    </html>
  );
}

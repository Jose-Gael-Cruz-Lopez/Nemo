import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Reeftrace | Source intelligence",
  description: "Observe, model, and explain potential debris sources.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ESB Portal | Effective School Boards",
    template: "%s | ESB Portal",
  },
  description: "The Effective School Boards practitioner and client portal — Great on Their Behalf Index, IRR Simulator, certified assessments, and more.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}

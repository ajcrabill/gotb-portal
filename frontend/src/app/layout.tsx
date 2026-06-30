import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ESB Portal | Effective School Boards",
    template: "%s | ESB Portal",
  },
  description: "The Effective School Boards practitioner and client portal — Great on Their Behalf Index, IRR Simulator, certified assessments, and more.",
  robots: { index: false, follow: false },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}

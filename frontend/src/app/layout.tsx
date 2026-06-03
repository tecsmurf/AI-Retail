import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "PurpleSol — AI Retail Intelligence Platform",
  description:
    "Transform CCTV footage into real-time retail analytics, customer journey intelligence, and conversion insights. Google Analytics for Physical Retail.",
  keywords: [
    "retail analytics",
    "customer journey",
    "CCTV analytics",
    "computer vision",
    "retail intelligence",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased dark`}>
      <body className="min-h-full bg-[var(--bg-primary)] text-[var(--text-primary)] font-[var(--font-inter)]">
        {children}
      </body>
    </html>
  );
}

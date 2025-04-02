// app/layout.tsx

import "../../app/globals.css";
import type React from "react";
import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { ThemeProvider } from "@/components/layout/theme-provider";
import { WebSocketProvider } from "@/contexts/websocket-context";
import { Toaster } from "@/components/ui/toaster";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: {
    default: "AI Council Dashboard",
    template: "%s | AI Council Dashboard",
  },
  description:
    "Real-time monitoring and control interface for AI agent debates",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          <WebSocketProvider
            url={process.env.NEXT_PUBLIC_WS_URL}
            maxReconnectAttempts={15}
            reconnectInterval={1500}
            reconnectBackoffMultiplier={1.3}
          >
            {children}
            <Toaster />
          </WebSocketProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}

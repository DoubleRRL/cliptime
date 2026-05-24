"use client";

import { ThemeProvider } from "next-themes";
import { MotionConfig } from "motion/react";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} storageKey="supoclip-theme">
      <MotionConfig
        reducedMotion="user"
        transition={{ type: "spring", stiffness: 380, damping: 32, mass: 0.8 }}
      >
        {children}
      </MotionConfig>
    </ThemeProvider>
  );
}

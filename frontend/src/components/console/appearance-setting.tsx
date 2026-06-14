"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export function AppearanceSetting() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const isDark = mounted ? (theme === "system" ? resolvedTheme : theme) !== "light" : true;

  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">Appearance</Label>
      <div className="flex gap-2">
        <Button
          type="button"
          variant={!isDark ? "default" : "outline"}
          className={cn(
            "flex-1",
            !isDark && "bg-[var(--console-terracotta)] hover:bg-[var(--console-terracotta-muted)]",
          )}
          disabled={!mounted}
          onClick={() => setTheme("light")}
        >
          <Sun className="mr-2 h-4 w-4" />
          Light
        </Button>
        <Button
          type="button"
          variant={isDark ? "default" : "outline"}
          className={cn(
            "flex-1",
            isDark && "bg-[var(--console-terracotta)] hover:bg-[var(--console-terracotta-muted)]",
          )}
          disabled={!mounted}
          onClick={() => setTheme("dark")}
        >
          <Moon className="mr-2 h-4 w-4" />
          Dark
        </Button>
      </div>
    </div>
  );
}

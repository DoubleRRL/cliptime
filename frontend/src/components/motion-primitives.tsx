"use client";

import { motion, type HTMLMotionProps } from "motion/react";

export const motionSpring = {
  type: "spring" as const,
  stiffness: 380,
  damping: 32,
  mass: 0.8,
};

export function MotionFadeIn({
  children,
  className,
  delay = 0,
  ...props
}: HTMLMotionProps<"div"> & { delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10, filter: "blur(4px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={{ ...motionSpring, delay }}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function MotionCard({
  children,
  className,
  layout = false,
  ...props
}: HTMLMotionProps<"div"> & { layout?: boolean }) {
  return (
    <motion.div
      layout={layout}
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      whileHover={{ y: -2 }}
      transition={motionSpring}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function MotionModalContent({
  children,
  className,
  ...props
}: HTMLMotionProps<"div">) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96, filter: "blur(4px)" }}
      animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
      exit={{ opacity: 0, scale: 0.96, filter: "blur(4px)" }}
      transition={motionSpring}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function MotionPage({
  children,
  className,
  ...props
}: HTMLMotionProps<"main">) {
  return (
    <motion.main
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -12 }}
      transition={{ type: "spring", stiffness: 320, damping: 34 }}
      className={className}
      {...props}
    >
      {children}
    </motion.main>
  );
}

export function MotionShake({
  children,
  shake,
  className,
}: {
  children: React.ReactNode;
  shake?: boolean;
  className?: string;
}) {
  return (
    <motion.div
      animate={
        shake
          ? { x: [0, -8, 8, -6, 6, -3, 3, 0] }
          : { x: 0 }
      }
      transition={{ duration: 0.45, ease: [0.36, 0.07, 0.19, 0.97] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function MotionNumber({
  value,
  className,
}: {
  value: number | string;
  className?: string;
}) {
  return (
    <motion.span
      key={String(value)}
      initial={{ opacity: 0, y: 8, filter: "blur(6px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={motionSpring}
      className={className}
    >
      {value}
    </motion.span>
  );
}

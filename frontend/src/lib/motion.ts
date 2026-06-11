import type { Transition, Variants } from "motion/react";

/** Snappy spring for buttons, toggles, badges. */
export const springSnappy: Transition = {
  type: "spring",
  stiffness: 500,
  damping: 32,
  mass: 0.7,
};

/** Gentle spring for panels, modals, drawers. */
export const springGentle: Transition = {
  type: "spring",
  stiffness: 260,
  damping: 28,
  mass: 1,
};

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: springGentle },
  exit: { opacity: 0, y: -8, transition: { duration: 0.15 } },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1, transition: springGentle },
  exit: { opacity: 0, scale: 0.97, transition: { duration: 0.12 } },
};

export const staggerChildren: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05 } },
};

/** whileTap/whileHover presets for interactive cards and buttons. */
export const pressable = {
  whileTap: { scale: 0.97 },
  transition: springSnappy,
} as const;

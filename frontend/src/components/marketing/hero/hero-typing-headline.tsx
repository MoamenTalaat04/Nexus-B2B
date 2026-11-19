"use client";

import { useReducedMotion } from "motion/react";
import { useTheme } from "next-themes";
import { useEffect, useState, useSyncExternalStore } from "react";
import { AuroraText } from "@/components/ui/aurora-text";

const emptySubscribe = () => () => {};

const LINE_1 = "Find the right customers.";
const LINE_2_PREFIX = "Let AI build the ";
const LINE_2_HIGHLIGHT = "connections.";
const FULL_TEXT = `${LINE_1}\n${LINE_2_PREFIX}${LINE_2_HIGHLIGHT}`;

const TYPE_MS = 48;
const DELETE_MS = 28;
const PAUSE_END_MS = 2000;
const PAUSE_START_MS = 350;

export function HeroTypingHeadline() {
  const { resolvedTheme } = useTheme();
  const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false);
  const isDark = !mounted || resolvedTheme === "dark";
  const shouldReduceMotion = useReducedMotion();
  const [count, setCount] = useState(FULL_TEXT.length);
  const [phase, setPhase] = useState<"pause_end" | "deleting" | "pause_start" | "typing">("pause_end");

  useEffect(() => {
    if (shouldReduceMotion) return;

    let timer: ReturnType<typeof setTimeout>;
    if (phase === "typing") {
      if (count < FULL_TEXT.length) {
        timer = setTimeout(() => setCount((c) => c + 1), TYPE_MS);
      } else {
        timer = setTimeout(() => setPhase("pause_end"), 0);
      }
    } else if (phase === "pause_end") {
      timer = setTimeout(() => setPhase("deleting"), PAUSE_END_MS);
    } else if (phase === "deleting") {
      if (count > 0) {
        timer = setTimeout(() => setCount((c) => c - 1), DELETE_MS);
      } else {
        timer = setTimeout(() => setPhase("pause_start"), 0);
      }
    } else {
      timer = setTimeout(() => setPhase("typing"), PAUSE_START_MS);
    }

    return () => clearTimeout(timer);
  }, [count, phase, shouldReduceMotion]);

  const effectiveCount = shouldReduceMotion ? FULL_TEXT.length : count;

  const line1End = LINE_1.length;
  const line2Start = line1End + 1; // after '\n'
  const highlightStart = line2Start + LINE_2_PREFIX.length;

  const line1Text = LINE_1.slice(0, Math.min(effectiveCount, line1End));
  const line2PrefixText =
    effectiveCount > line2Start
      ? LINE_2_PREFIX.slice(0, Math.min(effectiveCount - line2Start, LINE_2_PREFIX.length))
      : "";
  const highlightText =
    effectiveCount > highlightStart
      ? LINE_2_HIGHLIGHT.slice(0, effectiveCount - highlightStart)
      : "";

  const isOnLine2 = effectiveCount >= line2Start;

  const cursor = !shouldReduceMotion ? (
    <span
      aria-hidden="true"
      className="ml-1 inline-block h-[0.9em] w-[3px] translate-y-[0.08em] animate-pulse bg-emerald-600 dark:bg-[#D9FF83]"
    />
  ) : null;

  return (
    <h1 className="min-h-[2.3em] text-[clamp(2.15rem,4.5vw,3.75rem)] leading-[1.12] font-extrabold tracking-tight text-foreground dark:text-white">
      <span className="sr-only">{`${LINE_1} ${LINE_2_PREFIX}${LINE_2_HIGHLIGHT}`}</span>
      <span aria-hidden="true" className="block min-h-[1.12em]">
        {line1Text}
        {!isOnLine2 && cursor}
      </span>
      <span aria-hidden="true" className="block min-h-[1.12em]">
        {line2PrefixText}
        {highlightText && (
          <AuroraText
            colors={
              isDark
                ? ["#D9FF83", "#ECFFB8", "#BEF264", "#86EFAC"]
                : ["#079669", "#65A30D", "#84CC16", "#10B981"]
            }
            speed={1.2}
            className="font-extrabold"
          >
            {highlightText}
          </AuroraText>
        )}
        {isOnLine2 && cursor}
      </span>
    </h1>
  );
}


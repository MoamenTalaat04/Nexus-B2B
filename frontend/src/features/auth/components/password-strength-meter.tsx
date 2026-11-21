"use client";

import { CheckCircle2, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface PasswordCriteriaResult {
  minLength: boolean;
  maxLength: boolean;
  hasUpperAndLower: boolean;
  hasNumber: boolean;
  hasSpecial: boolean;
  passwordsMatch: boolean;
  score: number;
  label: "Weak" | "Medium" | "Strong" | "Very Strong";
  isValid: boolean;
}

export function evaluatePassword(password: string, confirmPassword: string): PasswordCriteriaResult {
  const minLength = password.length >= 8;
  const maxLength = password.length <= 72;
  const hasUpperAndLower = /[a-z]/.test(password) && /[A-Z]/.test(password);
  const hasNumber = /\d/.test(password);
  const hasSpecial = /[^A-Za-z0-9]/.test(password);
  const passwordsMatch = password.length > 0 && password === confirmPassword;

  // Count satisfied criteria sequentially (1..4) regardless of which rule the user types first.
  let score = 0;
  if (minLength && maxLength) score += 1;
  if (hasUpperAndLower) score += 1;
  if (hasNumber) score += 1;
  if (hasSpecial) score += 1;

  // Ensure any non-empty password shows at least 1 ("Weak") bar on the left.
  const displayScore = password.length > 0 ? Math.max(1, score) : 0;

  const label: PasswordCriteriaResult["label"] =
    displayScore <= 1 ? "Weak" : displayScore === 2 ? "Medium" : displayScore === 3 ? "Strong" : "Very Strong";

  const isValid = minLength && maxLength && hasUpperAndLower && hasNumber && hasSpecial && passwordsMatch;

  return {
    minLength,
    maxLength,
    hasUpperAndLower,
    hasNumber,
    hasSpecial,
    passwordsMatch,
    score: displayScore,
    label,
    isValid,
  };
}

const STEP_SOLID_COLORS: Record<number, string> = {
  1: "bg-red-500",
  2: "bg-yellow-400",
  3: "bg-lime-400",
  4: "bg-green-500",
};

const LABEL_COLORS: Record<PasswordCriteriaResult["label"], string> = {
  Weak: "text-red-600 dark:text-red-400",
  Medium: "text-yellow-600 dark:text-yellow-400",
  Strong: "text-lime-600 dark:text-lime-400",
  "Very Strong": "text-green-600 dark:text-green-400",
};

export function PasswordStrengthMeter({
  password,
  confirmPassword,
}: {
  password: string;
  confirmPassword: string;
}) {
  const evaluation = evaluatePassword(password, confirmPassword);
  const hasInput = password.length > 0 || confirmPassword.length > 0;

  const criteria = [
    { key: "length", label: "8–72 characters long", met: evaluation.minLength && evaluation.maxLength },
    { key: "case", label: "Uppercase & lowercase letters (A-Z, a-z)", met: evaluation.hasUpperAndLower },
    { key: "number", label: "At least one number (0-9)", met: evaluation.hasNumber },
    { key: "special", label: "At least one special character (!@#$…)", met: evaluation.hasSpecial },
    { key: "match", label: "Passwords match", met: evaluation.passwordsMatch },
  ];

  return (
    <div className="space-y-2.5 rounded-xl border border-border/80 bg-surface/60 p-3 dark:border-[#223D27] dark:bg-[#0A140C]/80">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
          Password strength
        </span>
        <span
          className={cn(
            "text-xs font-semibold",
            hasInput ? LABEL_COLORS[evaluation.label] : "text-muted-foreground",
          )}
        >
          {hasInput ? evaluation.label : "Enter password"}
        </span>
      </div>

      <div className="grid grid-cols-4 gap-1.5" aria-hidden="true">
        {[1, 2, 3, 4].map((step) => (
          <div
            key={step}
            className={cn(
              "h-1.5 rounded-full transition-colors duration-300",
              hasInput && evaluation.score >= step
                ? STEP_SOLID_COLORS[step]
                : "bg-border dark:bg-[#1D3321]",
            )}
          />
        ))}
      </div>

      <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">
        {criteria.map((item) => (
          <li
            key={item.key}
            className={cn(
              "flex items-center gap-1.5 text-[11px] transition-colors",
              item.met
                ? "font-medium text-emerald-700 dark:text-lime-300"
                : "text-muted-foreground dark:text-lime-200/55",
            )}
          >
            {item.met ? (
              <CheckCircle2 className="size-3.5 shrink-0 text-emerald-600 dark:text-lime-400" />
            ) : (
              <Circle className="size-3.5 shrink-0 opacity-50" />
            )}
            <span>{item.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

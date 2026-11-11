import { cn } from "@/lib/utils";

/**
 * Footrail mark: three footstep dots climbing to the right, a trail that
 * ends in a highlighted point. Pure SVG so it works in server components.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cn("h-8 w-8", className)}>
      <rect width="32" height="32" rx="9" fill="#5b3df5" />
      <circle cx="9" cy="22" r="2.6" fill="#fff" opacity="0.45" />
      <circle cx="15.5" cy="16.5" r="2.6" fill="#fff" opacity="0.7" />
      <circle cx="22.5" cy="10.5" r="3.4" fill="#5ef0b4" />
    </svg>
  );
}

export function Wordmark({ className, markClassName }: { className?: string; markClassName?: string }) {
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <LogoMark className={markClassName} />
      <span className="font-semibold tracking-tight">Footrail</span>
    </span>
  );
}

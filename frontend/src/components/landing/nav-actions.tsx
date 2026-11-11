"use client";

import Link from "next/link";
import { useSession } from "@/components/session";

/** Shows "Open dashboard" to a signed-in user and "Sign in" to everyone else. */
export function NavActions() {
  const { user } = useSession();
  return user ? (
    <Link href="/overview" className="lp-btn lp-btn-dark">Open dashboard</Link>
  ) : (
    <Link href="/login" className="lp-btn lp-btn-ghost">Sign in</Link>
  );
}

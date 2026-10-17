"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Re-reads the snapshot once a minute (the VM pushes one a minute), and only while the tab is visible: a hidden tab
// costs no Upstash bandwidth (free plan: 10 GB a month). Coming back to the tab refreshes at once.
export default function Refresh() {
  const router = useRouter();
  useEffect(() => {
    const tick = () => { if (document.visibilityState === "visible") router.refresh(); };
    const id = setInterval(tick, 60_000);
    document.addEventListener("visibilitychange", tick);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", tick); };
  }, [router]);
  return null;
}

"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Re-reads the snapshot every 30 seconds (the VM pushes one a minute).
export default function Refresh() {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => router.refresh(), 30_000);
    return () => clearInterval(id);
  }, [router]);
  return null;
}

import { useQuery } from "@tanstack/react-query";
import { fetchDeskData } from "@/lib/desk-data";
import type { DeskSnapshot } from "@/lib/live-data";

/**
 * React Query hook that fetches live desk data from /api/desk.
 * - Refetches every 5 minutes (300 000 ms).
 * - Falls back to static data in desk-data.ts on error.
 */
export function useDeskData() {
  return useQuery<DeskSnapshot | null>({
    queryKey: ["desk-snapshot"],
    queryFn: fetchDeskData,
    refetchInterval: 5 * 60 * 1000, // re-fetch every 5 minutes
    staleTime: 2 * 60 * 1000,       // data considered fresh for 2 min
    retry: 2,
  });
}

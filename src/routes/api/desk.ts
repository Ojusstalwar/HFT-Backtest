import { json } from "@tanstack/react-start";
// @ts-ignore
import { createAPIFileRoute } from "@tanstack/react-start/api";
import { buildSnapshot } from "../../lib/live-data";

export const APIRoute = createAPIFileRoute("/api/desk")({
  GET: async () => {
    const snapshot = buildSnapshot();
    return json(snapshot, {
      headers: {
        "Cache-Control": "public, s-maxage=300, stale-while-revalidate=600",
      },
    });
  },
});

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function passthroughHeaders(upstream: Response) {
  const headers = new Headers();
  headers.set("Content-Type", upstream.headers.get("Content-Type") ?? "text/event-stream; charset=utf-8");
  headers.set("Cache-Control", "no-cache, no-transform");
  headers.set("Connection", "keep-alive");
  return headers;
}

export async function POST(req: Request) {
  const agentUrl = process.env.AGENT_SERVICE_URL || "http://localhost:8100/agui";
  const body = await req.text();

  const upstream = await fetch(agentUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body,
    // В Node runtime duplex иногда нужен для стриминга (зависит от версии).
    // @ts-expect-error duplex required for fetch streaming in Node
    duplex: "half",
  });

  return new Response(upstream.body, {
    status: upstream.status,
    headers: passthroughHeaders(upstream),
  });
}


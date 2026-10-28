import { describe, expect, it } from "vitest";
import { Client } from "../src/client";
import type { FetchLike } from "../src/base";

const API_KEY = "hs_live_xxxxxxxx";
const UPPER_UUID = /^[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}$/;

class Script {
  readonly requests: URL[] = [];
  private readonly replies: Response[];

  constructor(...replies: Response[]) {
    this.replies = replies;
  }

  fetch: FetchLike = async (url) => {
    this.requests.push(new URL(url));
    return this.replies.shift()!;
  };
}

function ok(data: unknown): Response {
  return new Response(JSON.stringify(data), {
    status: 200,
  });
}

function pageReply(
  items: unknown[],
  nextCursor: string | null = null,
): Response {
  return ok({ items, next_cursor: nextCursor, has_more: nextCursor !== null });
}

function searchTopReply(
  edges: unknown[],
  nextCursor: string | null = null,
): Response {
  return ok({ edges, next_cursor: nextCursor, search_context: {} });
}

function client(script: Script): Client {
  return new Client({ apiKey: API_KEY, rateLimit: null, fetch: script.fetch });
}

describe("Client", () => {
  it("returns the unwrapped object for a lookup endpoint", async () => {
    const script = new Script(ok({ pk: "123", username: "nike" }));
    expect(await client(script).user({ userId: "123" })).toEqual({
      pk: "123",
      username: "nike",
    });
    expect(script.requests[0]!.pathname).toBe("/users/123");
  });

  it("auto-generates the search session ids", async () => {
    const script = new Script(pageReply([]));
    await client(script).searchUsers({ query: "nike" });
    const params = script.requests[0]!.searchParams;
    expect(params.get("query")).toBe("nike");
    expect(params.get("search_session_id")).toMatch(UPPER_UUID);
    expect(params.get("serp_session_id")).toMatch(UPPER_UUID);
    expect(params.get("search_session_id")).not.toBe(
      params.get("serp_session_id"),
    );
    expect(params.has("cursor")).toBe(false);
  });

  it("returns the raw feed dict for userPosts, with no cursor param", async () => {
    const feed = {
      items: [{ pk: "1" }, { pk: "2" }],
      profile_grid_items_cursor: "c2",
      more_available: true,
    };
    const script = new Script(ok(feed));
    expect(await client(script).userPosts({ userId: "123" })).toEqual(feed);
    expect(script.requests[0]!.pathname).toBe("/users/123/posts");
    expect(script.requests[0]!.searchParams.has("cursor")).toBe(false);
  });

  it("has no iterUserPosts iterator (single-call only)", () => {
    const c = client(new Script()) as unknown as Record<string, unknown>;
    expect(typeof c["userPosts"]).toBe("function");
    expect(c["iterUserPosts"]).toBeUndefined();
  });

  it("iterSearchTop replays the query and session ids on page two", async () => {
    const script = new Script(
      searchTopReply([{ id: "a" }], "c2"),
      searchTopReply([{ id: "b" }]),
    );
    const edges: unknown[] = [];
    for await (const edge of client(script).iterSearchTop({ query: "nike" })) {
      edges.push(edge);
    }
    expect(edges).toEqual([{ id: "a" }, { id: "b" }]);

    const first = Object.fromEntries(script.requests[0]!.searchParams);
    const second = Object.fromEntries(script.requests[1]!.searchParams);
    expect(first["query"]).toBe("nike");
    expect(first["search_session_id"]).toMatch(UPPER_UUID);
    expect(first["serp_session_id"]).toMatch(UPPER_UUID);
    expect("cursor" in first).toBe(false);
    expect(second).toEqual({ ...first, cursor: "c2" });
  });
});

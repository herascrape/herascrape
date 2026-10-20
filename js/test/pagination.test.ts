import { describe, expect, it } from "vitest";
import { paginate } from "../src/pagination";

type Page = Record<string, unknown>;

function page(
  ids: number[],
  opts: { cursor: string | null; more: boolean; key?: string },
): Page {
  return {
    [opts.key ?? "items"]: ids.map((id) => ({ id })),
    next_cursor: opts.cursor,
    has_more: opts.more,
  };
}

function searchPage(ids: number[], cursor: string | null): Page {
  return { edges: ids.map((id) => ({ id })), next_cursor: cursor };
}

class Script {
  readonly cursors: (string | undefined)[] = [];
  private readonly pages: Page[];

  constructor(...pages: Page[]) {
    this.pages = pages;
  }

  fetch = async (cursor: string | undefined): Promise<Page> => {
    this.cursors.push(cursor);
    return this.pages[this.cursors.length - 1]!;
  };
}

async function collect(
  script: Script,
  opts: { itemKey?: string; maxItems?: number | null } = {},
): Promise<number[]> {
  const out: number[] = [];
  for await (const item of paginate(script.fetch, opts)) {
    out.push((item as { id: number }).id);
  }
  return out;
}

describe("paginate", () => {
  it("walks two pages, threading the cursor", async () => {
    const script = new Script(
      page([1, 2], { cursor: "c1", more: true }),
      page([3], { cursor: null, more: false }),
    );
    expect(await collect(script)).toEqual([1, 2, 3]);
    expect(script.cursors).toEqual([undefined, "c1"]);
  });

  it("advances past an empty page that still has_more", async () => {
    const script = new Script(
      page([], { cursor: "c1", more: true }),
      page([9], { cursor: null, more: false }),
    );
    expect(await collect(script)).toEqual([9]);
    expect(script.cursors).toEqual([undefined, "c1"]);
  });

  it("stops on a null cursor even if has_more is true", async () => {
    const script = new Script(page([1], { cursor: null, more: true }));
    expect(await collect(script)).toEqual([1]);
    expect(script.cursors).toEqual([undefined]);
  });

  it("stops when has_more is false even if a cursor is set", async () => {
    const script = new Script(page([1], { cursor: "c1", more: false }));
    expect(await collect(script)).toEqual([1]);
    expect(script.cursors).toEqual([undefined]);
  });

  it("handles the search/top shape: edges and no has_more", async () => {
    const script = new Script(searchPage([1, 2], "c1"), searchPage([3], null));
    expect(await collect(script, { itemKey: "edges" })).toEqual([1, 2, 3]);
    expect(script.cursors).toEqual([undefined, "c1"]);
  });

  it("truncates mid-page at maxItems", async () => {
    const script = new Script(page([1, 2, 3], { cursor: "c1", more: true }));
    expect(await collect(script, { maxItems: 2 })).toEqual([1, 2]);
    expect(script.cursors).toEqual([undefined]);
  });

  it("stops at a maxItems page boundary without fetching again", async () => {
    const script = new Script(page([1, 2], { cursor: "c1", more: true }));
    expect(await collect(script, { maxItems: 2 })).toEqual([1, 2]);
    expect(script.cursors).toEqual([undefined]);
  });

  it("fetches nothing when maxItems is zero", async () => {
    const script = new Script();
    expect(await collect(script, { maxItems: 0 })).toEqual([]);
    expect(script.cursors).toEqual([]);
  });

  it("is lazy: no fetch until the first pull", async () => {
    const script = new Script(
      page([1, 2], { cursor: "c1", more: true }),
      page([3], { cursor: null, more: false }),
    );
    const iterator = paginate(script.fetch)[Symbol.asyncIterator]();
    expect(script.cursors).toEqual([]);
    expect((await iterator.next()).value).toEqual({ id: 1 });
    expect((await iterator.next()).value).toEqual({ id: 2 });
    expect(script.cursors).toEqual([undefined]);
    expect((await iterator.next()).value).toEqual({ id: 3 });
    expect(script.cursors).toEqual([undefined, "c1"]);
  });
});

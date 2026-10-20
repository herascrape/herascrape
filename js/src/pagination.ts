type Page = Record<string, unknown>;
type Item = Record<string, unknown>;

export type FetchPage = (cursor: string | undefined) => Promise<Page>;

function nextCursor(page: Page): string | null {
  const raw = page["next_cursor"];
  const cursor = typeof raw === "string" ? raw : null;
  const hasMore =
    "has_more" in page ? Boolean(page["has_more"]) : cursor !== null;
  return hasMore ? cursor : null;
}

/**
 * Lazily yield `page[itemKey]` across pages, up to `maxItems`. Stops on a
 * null `next_cursor`, tolerating a page with no `has_more` (search/top).
 */
export async function* paginate(
  fetchPage: FetchPage,
  opts: { itemKey?: string; maxItems?: number | null } = {},
): AsyncIterableIterator<Item> {
  const itemKey = opts.itemKey ?? "items";
  const maxItems = opts.maxItems ?? null;
  let yielded = 0;
  let cursor: string | undefined = undefined;
  while (maxItems === null || yielded < maxItems) {
    const page = await fetchPage(cursor);
    const items = (page[itemKey] ?? []) as Item[];
    for (const item of items) {
      yield item;
      yielded += 1;
      if (maxItems !== null && yielded >= maxItems) return;
    }
    const next = nextCursor(page);
    if (next === null) return;
    cursor = next;
  }
}

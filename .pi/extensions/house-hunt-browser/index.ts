import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { promises as fs } from "node:fs";
import path from "node:path";

const DEFAULT_SITES = ["rightmove.co.uk", "zoopla.co.uk", "onthemarket.com"] as const;
const FEATURE_KEYWORDS = [
  "parking",
  "garden",
  "garage",
  "walkable",
  "quiet street",
  "balcony",
  "lift",
] as const;

const searchParams = Type.Object({
  query: Type.String({ description: "Search query or buyer brief for finding listings" }),
  maxResults: Type.Optional(Type.Integer({ minimum: 1, maximum: 20, default: 8 })),
  sites: Type.Optional(Type.Array(Type.String({ description: "Domain to include" }))),
});

const extractParams = Type.Object({
  url: Type.String({ description: "Property listing URL" }),
  commuteMinutes: Type.Optional(Type.Integer({ minimum: 0, description: "Known commute time if already computed elsewhere" })),
});

const listingSchema = Type.Object({
  id: Type.String(),
  title: Type.String(),
  price: Type.Integer(),
  bedrooms: Type.Integer(),
  bathrooms: Type.Integer(),
  location: Type.String(),
  commute_minutes: Type.Union([Type.Integer(), Type.Null()]),
  features: Type.Array(Type.String()),
  description: Type.String(),
  source_url: Type.String(),
});

const runParams = Type.Object({
  brief: Type.String({ description: "Buyer brief in plain English" }),
  listings: Type.Array(listingSchema, { minItems: 1, description: "Normalized listings to rank" }),
  exportHtmlPath: Type.Optional(Type.String({ description: "Optional HTML export path" })),
  exportCsvPath: Type.Optional(Type.String({ description: "Optional CSV export path" })),
});

type ListingDict = {
  id: string;
  title: string;
  price: number;
  bedrooms: number;
  bathrooms: number;
  location: string;
  commute_minutes: number | null;
  features: string[];
  description: string;
  source_url: string;
};

export default function houseHuntBrowserExtension(pi: ExtensionAPI) {
  pi.registerTool({
    name: "property_web_search",
    label: "Property Web Search",
    description: "Search the web for property listing pages on Rightmove, Zoopla, OnTheMarket, and similar sources.",
    promptSnippet: "Search the web for property listing URLs that match a buyer brief.",
    promptGuidelines: [
      "Use this tool to gather candidate property listing URLs before normalizing them.",
      "After searching, use property_listing_extract on the most relevant results.",
    ],
    parameters: searchParams,
    async execute(_toolCallId, params, signal) {
      const results = await searchListings(params.query, params.maxResults ?? 8, params.sites ?? [...DEFAULT_SITES], signal);
      const summary = results.length === 0
        ? "No listing URLs found."
        : results.map((result, index) => `${index + 1}. ${result.title} — ${result.url}`).join("\n");
      return {
        content: [{ type: "text", text: summary }],
        details: { query: params.query, count: results.length, results },
      };
    },
  });

  pi.registerTool({
    name: "property_listing_extract",
    label: "Property Listing Extract",
    description: "Fetch a property listing page and normalize it into the house-hunt harness listing format.",
    promptSnippet: "Fetch a property page and extract normalized listing fields like price, beds, baths, location, features, description, and source URL.",
    promptGuidelines: [
      "Use this after property_web_search or when the user gives a listing URL.",
      "Do not invent missing values; leave commute_minutes null if you do not have it.",
    ],
    parameters: extractParams,
    async execute(_toolCallId, params, signal) {
      const listing = await extractListing(params.url, params.commuteMinutes ?? null, signal);
      return {
        content: [{ type: "text", text: JSON.stringify(listing, null, 2) }],
        details: { listing },
      };
    },
  });

  pi.registerTool({
    name: "run_house_hunt_harness",
    label: "Run House Hunt Harness",
    description: "Run the Python house-hunt harness on a buyer brief plus normalized listings.",
    promptSnippet: "Run the repo's house-hunt ranking, explanation, comparison, and next-steps pipeline on supplied listings.",
    promptGuidelines: [
      "Use this after collecting and normalizing candidate listings.",
      "Prefer 5-12 candidate listings when available.",
    ],
    parameters: runParams,
    async execute(_toolCallId, params, signal) {
      const tempDir = path.join(process.cwd(), ".tmp");
      await fs.mkdir(tempDir, { recursive: true });
      const listingsPath = path.join(tempDir, `house-hunt-${Date.now()}.json`);
      await fs.writeFile(listingsPath, JSON.stringify(params.listings, null, 2), "utf-8");

      const commandArgs = [
        "run",
        "--extra",
        "dev",
        "python",
        ".pi/skills/browser-house-hunt/run_house_hunt.py",
        "--brief",
        params.brief,
        "--listings-file",
        listingsPath,
      ];
      if (params.exportHtmlPath) {
        commandArgs.push("--export-html", params.exportHtmlPath);
      }
      if (params.exportCsvPath) {
        commandArgs.push("--export-csv", params.exportCsvPath);
      }

      const result = await pi.exec("uv", commandArgs, { signal });
      const output = [result.stdout, result.stderr].filter(Boolean).join("\n").trim();
      return {
        content: [{ type: "text", text: output || "Harness completed with no output." }],
        details: {
          listingsPath,
          command: ["uv", ...commandArgs].join(" "),
          exitCode: result.code,
          killed: result.killed,
        },
        isError: result.code !== 0,
      };
    },
  });
}

async function searchListings(query: string, maxResults: number, sites: string[], signal?: AbortSignal) {
  const scopedQuery = `${query} ${sites.map((site) => `site:${site}`).join(" OR ")}`;
  const url = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(scopedQuery)}`;
  const response = await fetch(url, {
    headers: {
      "user-agent": "Mozilla/5.0 (compatible; house-hunt-browser-extension/0.1)",
      "accept-language": "en-GB,en;q=0.9",
    },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Search failed: HTTP ${response.status}`);
  }
  const html = await response.text();
  const results: Array<{ title: string; url: string }> = [];
  const anchorRegex = /<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi;
  let match: RegExpExecArray | null;
  while ((match = anchorRegex.exec(html)) && results.length < maxResults * 3) {
    const url = unwrapDuckDuckGoUrl(decodeHtml(match[1]));
    if (!url) continue;
    if (!sites.some((site) => hostnameMatches(url, site))) continue;
    const title = stripTags(decodeHtml(match[2])).trim();
    if (!title) continue;
    if (results.some((item) => item.url === url)) continue;
    results.push({ title, url });
  }
  return results.slice(0, maxResults);
}

async function extractListing(url: string, commuteMinutes: number | null, signal?: AbortSignal): Promise<ListingDict> {
  const response = await fetch(url, {
    headers: {
      "user-agent": "Mozilla/5.0 (compatible; house-hunt-browser-extension/0.1)",
      "accept-language": "en-GB,en;q=0.9",
    },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Listing fetch failed: HTTP ${response.status}`);
  }
  const html = await response.text();
  const jsonLdObjects = extractJsonLd(html);
  const mergedJsonLd = pickBestJsonLd(jsonLdObjects);
  const pageText = stripTags(removeScriptsAndStyles(html));

  const title = firstNonEmpty(
    stringAtPath(mergedJsonLd, ["name"]),
    extractMeta(html, "property=\"og:title\"", "content"),
    extractTitleTag(html),
    "Untitled listing",
  );
  const description = firstNonEmpty(
    stringAtPath(mergedJsonLd, ["description"]),
    extractMeta(html, "name=\"description\"", "content"),
    pageText.slice(0, 280).trim(),
    "",
  );
  const price = firstInt(
    numberAtPath(mergedJsonLd, ["offers", "price"]),
    numberAtPath(mergedJsonLd, ["offers", 0, "price"]),
    extractCurrencyInt(pageText),
    0,
  );
  const bedrooms = firstInt(
    numberAtPath(mergedJsonLd, ["numberOfRooms"]),
    regexInt(pageText, /(\d+)\s*(?:bed|bedroom)/i),
    0,
  );
  const bathrooms = firstInt(
    regexInt(pageText, /(\d+)\s*(?:bath|bathroom)/i),
    0,
  );
  const location = firstNonEmpty(
    stringAtPath(mergedJsonLd, ["address", "addressLocality"]),
    stringAtPath(mergedJsonLd, ["address", "streetAddress"]),
    inferLocationFromTitle(title),
    inferLocationFromText(pageText),
    "unknown",
  );
  const canonicalUrl = firstNonEmpty(
    stringAtPath(mergedJsonLd, ["url"]),
    extractCanonicalUrl(html),
    url,
  );
  const features = FEATURE_KEYWORDS.filter((keyword) => new RegExp(`\\b${escapeRegExp(keyword)}\\b`, "i").test(pageText));

  return {
    id: createListingId(canonicalUrl),
    title,
    price,
    bedrooms,
    bathrooms,
    location,
    commute_minutes: commuteMinutes,
    features,
    description,
    source_url: canonicalUrl,
  };
}

function extractJsonLd(html: string): any[] {
  const matches = [...html.matchAll(/<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/gi)];
  const parsed: any[] = [];
  for (const match of matches) {
    const raw = decodeHtml(match[1]).trim();
    if (!raw) continue;
    try {
      const value = JSON.parse(raw);
      parsed.push(value);
    } catch {
      continue;
    }
  }
  return parsed.flatMap((value) => Array.isArray(value) ? value : [value]);
}

function pickBestJsonLd(items: any[]): any {
  return items.find((item) => item && typeof item === "object" && (item.offers || item.address || item.name)) ?? {};
}

function extractMeta(html: string, attrSelector: string, targetAttr: string): string | undefined {
  const regex = new RegExp(`<meta[^>]*${attrSelector}[^>]*${targetAttr}="([^"]*)"[^>]*>`, "i");
  return regex.exec(html)?.[1];
}

function extractTitleTag(html: string): string | undefined {
  return stripTags((/<title[^>]*>([\s\S]*?)<\/title>/i.exec(html)?.[1] ?? "")).trim() || undefined;
}

function extractCanonicalUrl(html: string): string | undefined {
  return /<link[^>]*rel="canonical"[^>]*href="([^"]+)"[^>]*>/i.exec(html)?.[1];
}

function removeScriptsAndStyles(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ");
}

function stripTags(text: string): string {
  return text.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
}

function decodeHtml(text: string): string {
  return text
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#x2F;/g, "/");
}

function unwrapDuckDuckGoUrl(raw: string): string | undefined {
  try {
    const url = new URL(raw, "https://html.duckduckgo.com");
    const uddg = url.searchParams.get("uddg");
    return uddg ? decodeURIComponent(uddg) : url.toString();
  } catch {
    return undefined;
  }
}

function hostnameMatches(rawUrl: string, site: string): boolean {
  try {
    const host = new URL(rawUrl).hostname.replace(/^www\./, "");
    return host === site || host.endsWith(`.${site}`);
  } catch {
    return false;
  }
}

function stringAtPath(value: any, pathParts: Array<string | number>): string | undefined {
  let current = value;
  for (const part of pathParts) {
    if (current == null) return undefined;
    current = current[part as any];
  }
  return typeof current === "string" ? current.trim() || undefined : undefined;
}

function numberAtPath(value: any, pathParts: Array<string | number>): number | undefined {
  let current = value;
  for (const part of pathParts) {
    if (current == null) return undefined;
    current = current[part as any];
  }
  if (typeof current === "number") return current;
  if (typeof current === "string") return extractCurrencyInt(current) ?? regexInt(current, /(\d+)/);
  return undefined;
}

function extractCurrencyInt(text: string): number | undefined {
  const match = text.match(/£\s*([0-9][0-9,]*)/);
  if (!match) return undefined;
  return Number(match[1].replace(/,/g, ""));
}

function regexInt(text: string, regex: RegExp): number | undefined {
  const match = regex.exec(text);
  return match ? Number(match[1]) : undefined;
}

function firstNonEmpty(...values: Array<string | undefined>): string {
  for (const value of values) {
    if (value && value.trim()) return value.trim();
  }
  return "";
}

function firstInt(...values: Array<number | undefined>): number {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) return Math.round(value);
  }
  return 0;
}

function inferLocationFromTitle(title: string): string | undefined {
  const parts = title.split(/[|,-]/).map((part) => part.trim()).filter(Boolean);
  return parts.length > 1 ? parts[parts.length - 1] : undefined;
}

function inferLocationFromText(text: string): string | undefined {
  const match = text.match(/\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b/);
  return match?.[1];
}

function createListingId(rawUrl: string): string {
  try {
    const url = new URL(rawUrl);
    const slug = `${url.hostname}${url.pathname}`.replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    return slug || `listing-${Date.now()}`;
  } catch {
    return `listing-${Date.now()}`;
  }
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

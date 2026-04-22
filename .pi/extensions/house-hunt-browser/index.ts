import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { promises as fs } from "node:fs";
import path from "node:path";
import { extractListingFromHtml } from "./extractor-core.mjs";
import { enrichListingsWithCommute, inferCommuteDestinationFromBrief } from "./commute-core.mjs";

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

const batchExtractParams = Type.Object({
  urls: Type.Array(Type.String({ description: "Property listing URL" }), { minItems: 1, maxItems: 20 }),
  commuteMinutesByUrl: Type.Optional(Type.Record(Type.String(), Type.Integer({ minimum: 0 }))),
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
  external_refs: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
});

const runParams = Type.Object({
  brief: Type.String({ description: "Buyer brief in plain English" }),
  listings: Type.Array(listingSchema, { minItems: 1, description: "Normalized listings to rank" }),
  exportHtmlPath: Type.Optional(Type.String({ description: "Optional HTML export path" })),
  exportCsvPath: Type.Optional(Type.String({ description: "Optional CSV export path" })),
});

const webRunParams = Type.Object({
  brief: Type.String({ description: "Buyer brief in plain English" }),
  maxResults: Type.Optional(Type.Integer({ minimum: 1, maximum: 12, default: 6 })),
  sites: Type.Optional(Type.Array(Type.String({ description: "Domain to include" }))),
  minQualityScore: Type.Optional(Type.Integer({ minimum: 0, maximum: 100, default: 45, description: "Minimum extraction quality score required before sending listings into the harness" })),
  commuteDestination: Type.Optional(Type.String({ description: "Optional commute destination for estimating commute times before ranking" })),
  commuteMode: Type.Optional(Type.String({ description: "Optional commute mode: transit, driving, or walking" })),
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
  external_refs?: Record<string, unknown>;
};

type PartialListing = Partial<Omit<ListingDict, "commute_minutes">> & {
  commute_minutes?: number | null;
};

type ListingExtractionDiagnostics = {
  parser: string;
  sourceHints: string[];
  fieldSources: Record<string, string>;
  host?: string;
  hadJsonLd: boolean;
  missingFields: string[];
  warnings: string[];
  qualityScore: number;
};

type ListingExtractionResult = {
  listing: ListingDict;
  diagnostics: ListingExtractionDiagnostics;
};

export default function houseHuntBrowserExtension(pi: ExtensionAPI) {
  pi.registerCommand("house-hunt-smoke", {
    description: "Smoke-test the browser house-hunt flow: /house-hunt-smoke <buyer brief>",
    handler: async (args, ctx) => {
      const brief = args.trim();
      if (!brief) {
        ctx.ui.notify("Usage: /house-hunt-smoke <buyer brief>", "warning");
        return;
      }

      ctx.ui.notify("Running browser house-hunt smoke test...", "info");
      const result = await performWebHouseHunt(
        pi,
        brief,
        6,
        [...DEFAULT_SITES],
        45,
        inferCommuteDestinationFromBrief(brief) ?? undefined,
        "transit",
        undefined,
        undefined,
      );
      pi.sendMessage(
        {
          customType: "house-hunt-smoke",
          content: formatSmokeSummary(brief, result),
          display: true,
          details: result,
        },
        { triggerTurn: false, deliverAs: "nextTurn" },
      );
      ctx.ui.notify(`Smoke test complete. Trace: ${result.tracePath}`, result.isError ? "warning" : "success");
    },
  });

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
      const tracePath = await writeExtensionTrace("search", {
        query: params.query,
        count: results.length,
        results,
      });
      const summary = results.length === 0
        ? `No listing URLs found. Trace: ${tracePath}`
        : `${results.map((result, index) => `${index + 1}. ${result.title} — ${result.url}`).join("\n")}\n\nTrace: ${tracePath}`;
      return {
        content: [{ type: "text", text: summary }],
        details: { query: params.query, count: results.length, results, tracePath },
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
      const extraction = await extractListing(params.url, params.commuteMinutes ?? null, signal);
      const tracePath = await writeExtensionTrace("extract", extraction);
      return {
        content: [{ type: "text", text: `${JSON.stringify(extraction.listing, null, 2)}\n\nQuality: ${extraction.diagnostics.qualityScore}/100\nMissing: ${extraction.diagnostics.missingFields.join(', ') || 'none'}\nWarnings: ${extraction.diagnostics.warnings.join('; ') || 'none'}\nDiagnostics: ${JSON.stringify(extraction.diagnostics, null, 2)}\n\nTrace: ${tracePath}` }],
        details: { ...extraction, tracePath },
      };
    },
  });

  pi.registerTool({
    name: "extract_property_listings",
    label: "Extract Property Listings",
    description: "Fetch and normalize multiple property listing URLs into the house-hunt harness listing format.",
    promptSnippet: "Extract a batch of property listing URLs into normalized listing objects.",
    promptGuidelines: [
      "Use this when you already have several property URLs.",
      "Skip pages that cannot be fetched and keep the successful listings.",
    ],
    parameters: batchExtractParams,
    async execute(_toolCallId, params, signal) {
      const listings: ListingDict[] = [];
      const extracted: ListingExtractionResult[] = [];
      const failed: Array<{ url: string; error: string }> = [];
      for (const url of params.urls) {
        try {
          const extraction = await extractListing(url, params.commuteMinutesByUrl?.[url] ?? null, signal);
          listings.push(withExtractionRefs(extraction));
          extracted.push(extraction);
        } catch (error) {
          failed.push({ url, error: error instanceof Error ? error.message : String(error) });
        }
      }
      const tracePayload = { listings, extracted, failed };
      const tracePath = await writeExtensionTrace("batch-extract", tracePayload);
      return {
        content: [{ type: "text", text: JSON.stringify({ extracted: listings.length, failed: failed.length, listings, failed, tracePath }, null, 2) }],
        details: { listings, extracted, failed, tracePath },
        isError: listings.length === 0,
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
      const harness = await runHarness(
        pi,
        params.brief,
        params.listings,
        signal,
        params.exportHtmlPath,
        params.exportCsvPath,
      );
      const tracePath = await writeExtensionTrace("harness-run", harness.details);
      return {
        content: [{ type: "text", text: `${harness.output}\nTrace: ${tracePath}` }],
        details: { ...harness.details, tracePath },
        isError: harness.isError,
      };
    },
  });

  pi.registerTool({
    name: "house_hunt_from_web",
    label: "House Hunt From Web",
    description: "Search listing sites, extract candidate property pages, normalize them, and run the house-hunt harness in one step.",
    promptSnippet: "Search the web for property listings and run the full house-hunt harness workflow.",
    promptGuidelines: [
      "Use this for end-to-end browser-assisted house hunting.",
      "Report clearly when no pages could be extracted or when sites block access.",
    ],
    parameters: webRunParams,
    async execute(_toolCallId, params, signal) {
      const result = await performWebHouseHunt(
        pi,
        params.brief,
        params.maxResults ?? 6,
        params.sites ?? [...DEFAULT_SITES],
        params.minQualityScore ?? 45,
        params.commuteDestination ?? inferCommuteDestinationFromBrief(params.brief) ?? undefined,
        params.commuteMode ?? "transit",
        params.exportHtmlPath,
        params.exportCsvPath,
        signal,
      );
      const qualityLine = typeof result.averageQuality === "number"
        ? `Average extraction quality: ${result.averageQuality}/100\n${Array.isArray(result.qualityWarnings) && result.qualityWarnings.length > 0 ? `Quality warnings: ${result.qualityWarnings.join('; ')}\n` : ''}`
        : "";
      return {
        content: [{ type: "text", text: `${qualityLine}${result.output}\nTrace: ${result.tracePath}` }],
        details: result,
        isError: result.isError,
      };
    },
  });
}

async function performWebHouseHunt(
  pi: ExtensionAPI,
  brief: string,
  maxResults: number,
  sites: string[],
  minQualityScore: number,
  commuteDestination?: string,
  commuteMode: string = "transit",
  exportHtmlPath?: string,
  exportCsvPath?: string,
  signal?: AbortSignal,
): Promise<Record<string, unknown> & { output: string; tracePath: string; isError: boolean }> {
  const searchResults = await searchListings(brief, maxResults, sites, signal);
  const extracted: ListingExtractionResult[] = [];
  const failed: Array<{ url: string; error: string }> = [];

  for (const result of searchResults) {
    try {
      const extraction = await extractListing(result.url, null, signal);
      extracted.push(extraction);
    } catch (error) {
      failed.push({ url: result.url, error: error instanceof Error ? error.message : String(error) });
    }
  }

  const listings = enrichListingsWithCommute(
    extracted.map((item) => withExtractionRefs(item)),
    commuteDestination,
    commuteMode,
  );
  const acceptedExtractions = extracted.filter((item) => item.diagnostics.qualityScore >= minQualityScore);
  const acceptedListings = enrichListingsWithCommute(
    acceptedExtractions.map((item) => withExtractionRefs(item)),
    commuteDestination,
    commuteMode,
  );
  const filteredOutLowQuality = extracted
    .filter((item) => item.diagnostics.qualityScore < minQualityScore)
    .map((item) => ({
      title: item.listing.title,
      source_url: item.listing.source_url,
      qualityScore: item.diagnostics.qualityScore,
      warnings: item.diagnostics.warnings,
    }));

  if (listings.length === 0) {
    const tracePath = await writeExtensionTrace("web-run-failed", { searchResults, listings, extracted, failed, brief, minQualityScore, commuteDestination, commuteMode });
    return {
      output: `Search found ${searchResults.length} candidate URLs but none could be extracted. Failures: ${JSON.stringify(failed, null, 2)}`,
      searchResults,
      listings,
      extracted,
      failed,
      filteredOutLowQuality,
      minQualityScore,
      commuteDestination,
      commuteMode,
      tracePath,
      isError: true,
    };
  }

  if (acceptedListings.length === 0) {
    const tracePath = await writeExtensionTrace("web-run-quality-filtered", { searchResults, listings, extracted, failed, filteredOutLowQuality, brief, minQualityScore, commuteDestination, commuteMode });
    return {
      output: `Extracted ${listings.length} listing(s), but none met the minimum quality threshold of ${minQualityScore}/100.`,
      searchResults,
      listings,
      extracted,
      failed,
      filteredOutLowQuality,
      minQualityScore,
      commuteDestination,
      commuteMode,
      tracePath,
      isError: true,
    };
  }

  const harness = await runHarness(pi, brief, acceptedListings, signal, exportHtmlPath, exportCsvPath);
  const averageQuality = extracted.length > 0
    ? Math.round(extracted.reduce((sum, item) => sum + item.diagnostics.qualityScore, 0) / extracted.length)
    : 0;
  const lowQualityListings = filteredOutLowQuality;
  const qualityWarnings = [
    ...(averageQuality < 65 ? [`average extraction quality is low (${averageQuality}/100)`] : []),
    ...(lowQualityListings.length > 0 ? [`${lowQualityListings.length} listing(s) were filtered out below ${minQualityScore}/100`] : []),
  ];
  const details = {
    output: harness.output,
    searchResults,
    listings,
    acceptedListings,
    extracted,
    failed,
    averageQuality,
    minQualityScore,
    commuteDestination,
    commuteMode,
    lowQualityListings,
    qualityWarnings,
    ...harness.details,
    isError: harness.isError,
  };
  const tracePath = await writeExtensionTrace("web-run", details);
  return {
    ...details,
    tracePath,
    isError: harness.isError,
  };
}

function formatSmokeSummary(brief: string, result: Record<string, unknown> & { tracePath: string; isError: boolean }): string {
  const searchResults = Array.isArray(result.searchResults) ? result.searchResults as Array<{ title: string; url: string }> : [];
  const extracted = Array.isArray(result.extracted) ? result.extracted as ListingExtractionResult[] : [];
  const failed = Array.isArray(result.failed) ? result.failed as Array<{ url: string; error: string }> : [];
  const parserCounts = extracted.reduce<Record<string, number>>((acc, item) => {
    acc[item.diagnostics.parser] = (acc[item.diagnostics.parser] ?? 0) + 1;
    return acc;
  }, {});
  const averageQuality = extracted.length > 0
    ? Math.round(extracted.reduce((sum, item) => sum + item.diagnostics.qualityScore, 0) / extracted.length)
    : 0;

  return [
    "# House Hunt Smoke Test",
    "",
    `Brief: ${brief}`,
    `Search results: ${searchResults.length}`,
    `Extracted listings: ${extracted.length}`,
    `Failed extractions: ${failed.length}`,
    `Parser usage: ${Object.entries(parserCounts).map(([key, value]) => `${key}=${value}`).join(", ") || "none"}`,
    `Average extraction quality: ${averageQuality}/100`,
    ...(typeof result.minQualityScore === 'number' ? [`Minimum quality threshold: ${result.minQualityScore}/100`] : []),
    ...(Array.isArray(result.qualityWarnings) && result.qualityWarnings.length > 0 ? [`Quality warnings: ${result.qualityWarnings.join('; ')}`] : []),
    "",
    "Top extracted listings:",
    ...extracted.slice(0, 5).map((item, index) => `${index + 1}. ${item.listing.title} — ${item.listing.source_url} (${item.diagnostics.parser}, quality ${item.diagnostics.qualityScore}/100${item.diagnostics.warnings.length ? `, warnings: ${item.diagnostics.warnings.join('; ')}` : ''})`),
    ...(Array.isArray(result.filteredOutLowQuality) && result.filteredOutLowQuality.length > 0
      ? ["", "Filtered out for low quality:", ...(result.filteredOutLowQuality as Array<{ title: string; source_url: string; qualityScore: number }>).slice(0, 5).map((item) => `- ${item.title} — ${item.source_url} (${item.qualityScore}/100)`)]
      : []),
    ...(failed.length > 0 ? ["", "Failed URLs:", ...failed.slice(0, 5).map((item) => `- ${item.url}: ${item.error}`)] : []),
    "",
    `Trace: ${result.tracePath}`,
  ].join("\n");
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

async function extractListing(url: string, commuteMinutes: number | null, signal?: AbortSignal): Promise<ListingExtractionResult> {
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
  return extractListingFromHtml(url, html, commuteMinutes) as ListingExtractionResult;
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

function extractSiteSpecificListing(url: string, html: string, pageText: string, jsonLdObjects: any[]): PartialListing & { _parser?: string } {
  const host = safeHostname(url);
  if (!host) return { _parser: "generic" };
  if (host.endsWith("rightmove.co.uk")) {
    return { _parser: "rightmove", ...extractRightmoveListing(url, html, pageText, jsonLdObjects) };
  }
  if (host.endsWith("zoopla.co.uk")) {
    return { _parser: "zoopla", ...extractZooplaListing(url, html, pageText, jsonLdObjects) };
  }
  if (host.endsWith("onthemarket.com")) {
    return { _parser: "onthemarket", ...extractOnTheMarketListing(url, html, pageText, jsonLdObjects) };
  }
  return { _parser: "generic" };
}

function extractRightmoveListing(url: string, html: string, pageText: string, jsonLdObjects: any[]): PartialListing {
  const nextData = extractNextData(html);
  const pageModel = extractAssignedJson(html, /window\.PAGE_MODEL\s*=\s*/);
  const propertyData =
    findObject(nextData, (value) => typeof value?.id !== "undefined" && (value?.bedrooms || value?.bathrooms || value?.propertySubType))
    ?? findObject(pageModel, (value) => typeof value?.id !== "undefined" && (value?.bedrooms || value?.bathrooms || value?.propertySubType))
    ?? {};
  const features = normalizeFeatures([
    ...collectStrings(propertyData?.keyFeatures),
    ...collectStrings(findValue(nextData, (value) => Array.isArray(value) && value.some((item: unknown) => typeof item === "string" && /parking|garden|garage|balcony|lift/i.test(item))) ?? []),
  ]);
  return {
    id: firstNonEmpty(
      propertyData?.id != null ? `rightmove-${propertyData.id}` : undefined,
      createListingId(url),
    ),
    title: firstNonEmpty(
      propertyData?.headline,
      propertyData?.displayAddress,
      stringAtPath(pickBestJsonLd(jsonLdObjects), ["name"]),
    ),
    price: firstInt(
      coerceInt(propertyData?.prices?.primaryPrice),
      coerceInt(propertyData?.price),
      extractCurrencyInt(pageText),
    ),
    bedrooms: firstInt(coerceInt(propertyData?.bedrooms), regexInt(pageText, /(\d+)\s*(?:bed|bedroom)/i)),
    bathrooms: firstInt(coerceInt(propertyData?.bathrooms), regexInt(pageText, /(\d+)\s*(?:bath|bathroom)/i)),
    location: firstNonEmpty(propertyData?.displayAddress, propertyData?.address, inferLocationFromTitle(extractTitleTag(html) ?? "")),
    description: firstNonEmpty(propertyData?.summary, propertyData?.description, extractMeta(html, "name=\"description\"", "content")),
    features,
    source_url: firstNonEmpty(propertyData?.url, extractCanonicalUrl(html), url),
  };
}

function extractZooplaListing(url: string, html: string, pageText: string, jsonLdObjects: any[]): PartialListing {
  const nextData = extractNextData(html);
  const listing =
    findObject(nextData, (value) => (value?.listingId || value?.id) && (value?.price || value?.bedrooms || value?.branch))
    ?? findObject(nextData, (value) => (value?.price || value?.beds) && (value?.title || value?.address))
    ?? {};
  const features = normalizeFeatures([
    ...collectStrings(listing?.features),
    ...collectStrings(listing?.key_features),
    ...collectStrings(listing?.tags),
  ]);
  return {
    id: firstNonEmpty(
      listing?.listingId != null ? `zoopla-${listing.listingId}` : undefined,
      listing?.id != null ? `zoopla-${listing.id}` : undefined,
      createListingId(url),
    ),
    title: firstNonEmpty(listing?.title, listing?.propertyType, extractTitleTag(html)),
    price: firstInt(coerceInt(listing?.price), coerceInt(listing?.pricing?.value), extractCurrencyInt(pageText)),
    bedrooms: firstInt(coerceInt(listing?.beds), coerceInt(listing?.bedrooms), regexInt(pageText, /(\d+)\s*(?:bed|bedroom)/i)),
    bathrooms: firstInt(coerceInt(listing?.baths), coerceInt(listing?.bathrooms), regexInt(pageText, /(\d+)\s*(?:bath|bathroom)/i)),
    location: firstNonEmpty(
      listing?.address,
      listing?.location,
      listing?.branch?.displayAddress,
      stringAtPath(pickBestJsonLd(jsonLdObjects), ["address", "addressLocality"]),
    ),
    description: firstNonEmpty(listing?.description, extractMeta(html, "name=\"description\"", "content")),
    features,
    source_url: firstNonEmpty(listing?.canonicalUrl, extractCanonicalUrl(html), url),
  };
}

function extractOnTheMarketListing(url: string, html: string, pageText: string, jsonLdObjects: any[]): PartialListing {
  const nextData = extractNextData(html);
  const listing =
    findObject(nextData, (value) => (value?.id || value?.propertyId) && (value?.price || value?.bedrooms || value?.bathrooms))
    ?? findObject(nextData, (value) => (value?.price || value?.priceValue) && (value?.title || value?.displayAddress || value?.location))
    ?? {};
  const features = normalizeFeatures([
    ...collectStrings(listing?.keyFeatures),
    ...collectStrings(listing?.features),
    ...collectStrings(listing?.bulletPoints),
  ]);
  return {
    id: firstNonEmpty(
      listing?.id != null ? `onthemarket-${listing.id}` : undefined,
      listing?.propertyId != null ? `onthemarket-${listing.propertyId}` : undefined,
      createListingId(url),
    ),
    title: firstNonEmpty(listing?.title, listing?.heading, extractTitleTag(html)),
    price: firstInt(coerceInt(listing?.price), coerceInt(listing?.priceValue), extractCurrencyInt(pageText)),
    bedrooms: firstInt(coerceInt(listing?.bedrooms), regexInt(pageText, /(\d+)\s*(?:bed|bedroom)/i)),
    bathrooms: firstInt(coerceInt(listing?.bathrooms), regexInt(pageText, /(\d+)\s*(?:bath|bathroom)/i)),
    location: firstNonEmpty(listing?.displayAddress, listing?.location, listing?.address, inferLocationFromTitle(extractTitleTag(html) ?? "")),
    description: firstNonEmpty(listing?.description, listing?.summary, extractMeta(html, "name=\"description\"", "content")),
    features,
    source_url: firstNonEmpty(listing?.canonicalUrl, extractCanonicalUrl(html), url),
  };
}

function extractNextData(html: string): any {
  return extractScriptJson(html, /<script[^>]*id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/i) ?? {};
}

function extractScriptJson(html: string, regex: RegExp): any {
  const match = regex.exec(html);
  if (!match) return undefined;
  try {
    return JSON.parse(decodeHtml(match[1]));
  } catch {
    return undefined;
  }
}

function extractAssignedJson(html: string, prefixRegex: RegExp): any {
  const start = prefixRegex.exec(html);
  if (!start || start.index === undefined) return undefined;
  const from = start.index + start[0].length;
  const end = findBalancedJsonEnd(html, from);
  if (end === -1) return undefined;
  const raw = html.slice(from, end + 1);
  try {
    return JSON.parse(raw);
  } catch {
    return undefined;
  }
}

function findBalancedJsonEnd(text: string, start: number): number {
  let depth = 0;
  let inString = false;
  let escape = false;
  for (let i = start; i < text.length; i += 1) {
    const char = text[i];
    if (inString) {
      if (escape) {
        escape = false;
      } else if (char === "\\") {
        escape = true;
      } else if (char === '"') {
        inString = false;
      }
      continue;
    }
    if (char === '"') {
      inString = true;
      continue;
    }
    if (char === "{" || char === "[") depth += 1;
    if (char === "}" || char === "]") {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return -1;
}

function findObject(root: any, predicate: (value: any) => boolean): any {
  return findValue(root, (value) => !!value && typeof value === "object" && predicate(value));
}

function findValue(root: any, predicate: (value: any) => boolean): any {
  const seen = new Set<any>();
  const stack = [root];
  while (stack.length > 0) {
    const value = stack.pop();
    if (value == null || typeof value !== "object") continue;
    if (seen.has(value)) continue;
    seen.add(value);
    if (predicate(value)) return value;
    if (Array.isArray(value)) {
      for (const item of value) stack.push(item);
    } else {
      for (const item of Object.values(value)) stack.push(item);
    }
  }
  return undefined;
}

function collectStrings(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item === "string") return [item];
    if (item && typeof item === "object") {
      return Object.values(item).filter((v): v is string => typeof v === "string");
    }
    return [];
  });
}

function normalizeFeatures(values: string[]): string[] {
  const lowered = values.map((value) => value.trim()).filter(Boolean).join(" | ").toLowerCase();
  const synonyms: Record<(typeof FEATURE_KEYWORDS)[number], string[]> = {
    parking: ["parking", "off-street", "off street", "driveway", "allocated space"],
    garden: ["garden", "patio", "terrace", "outdoor space"],
    garage: ["garage"],
    walkable: ["walkable", "walking distance"],
    "quiet street": ["quiet street", "quiet road", "cul-de-sac"],
    balcony: ["balcony"],
    lift: ["lift", "elevator"],
  };
  return FEATURE_KEYWORDS.filter((keyword) => synonyms[keyword].some((term) => new RegExp(`\\b${escapeRegExp(term)}\\b`, "i").test(lowered)));
}

function coerceInt(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return Math.round(value);
  if (typeof value === "string") return extractCurrencyInt(value) ?? regexInt(value, /(\d+)/);
  return undefined;
}

function buildExtractionDiagnostics(
  url: string,
  jsonLdObjects: any[],
  siteSpecific: PartialListing & { _parser?: string },
): ListingExtractionDiagnostics {
  const sourceHints: string[] = [];
  const fieldSources: Record<string, string> = {};
  if (siteSpecific._parser && siteSpecific._parser !== "generic") {
    sourceHints.push(`site:${siteSpecific._parser}`);
  }
  for (const field of ["title", "description", "price", "bedrooms", "bathrooms", "location", "source_url"] as const) {
    if (siteSpecific[field] !== undefined && siteSpecific[field] !== "") {
      fieldSources[field] = "site_specific";
    } else if (jsonLdObjects.length > 0) {
      fieldSources[field] = "json_ld_or_fallback";
    } else {
      fieldSources[field] = "text_or_meta";
    }
    sourceHints.push(`${field}:${fieldSources[field]}`);
  }
  return {
    parser: siteSpecific._parser || "generic",
    sourceHints,
    fieldSources,
    host: safeHostname(url),
    hadJsonLd: jsonLdObjects.length > 0,
  };
}

function safeHostname(rawUrl: string): string | undefined {
  try {
    return new URL(rawUrl).hostname.replace(/^www\./, "");
  } catch {
    return undefined;
  }
}

function withExtractionRefs(extraction: ListingExtractionResult): ListingDict {
  return {
    ...extraction.listing,
    external_refs: {
      ...(extraction.listing.external_refs ?? {}),
      extraction_diagnostics: extraction.diagnostics,
      extraction_quality_score: extraction.diagnostics.qualityScore,
      extraction_parser: extraction.diagnostics.parser,
    },
  };
}

async function runHarness(
  pi: ExtensionAPI,
  brief: string,
  listings: ListingDict[],
  signal: AbortSignal | undefined,
  exportHtmlPath?: string,
  exportCsvPath?: string,
): Promise<{ output: string; details: Record<string, unknown>; isError: boolean }> {
  const tempDir = path.join(process.cwd(), ".tmp");
  await fs.mkdir(tempDir, { recursive: true });
  const listingsPath = path.join(tempDir, `house-hunt-${Date.now()}.json`);
  await fs.writeFile(listingsPath, JSON.stringify(listings, null, 2), "utf-8");

  const commandArgs = [
    "run",
    "--extra",
    "dev",
    "python",
    ".pi/skills/browser-house-hunt/run_house_hunt.py",
    "--brief",
    brief,
    "--listings-file",
    listingsPath,
  ];
  if (exportHtmlPath) commandArgs.push("--export-html", exportHtmlPath);
  if (exportCsvPath) commandArgs.push("--export-csv", exportCsvPath);

  const result = await pi.exec("uv", commandArgs, { signal });
  const output = [result.stdout, result.stderr].filter(Boolean).join("\n").trim() || "Harness completed with no output.";
  return {
    output,
    details: {
      listingsPath,
      command: ["uv", ...commandArgs].join(" "),
      exitCode: result.code,
      killed: result.killed,
    },
    isError: result.code !== 0,
  };
}

async function writeExtensionTrace(kind: string, payload: unknown): Promise<string> {
  const tempDir = path.join(process.cwd(), ".tmp");
  await fs.mkdir(tempDir, { recursive: true });
  const tracePath = path.join(tempDir, `house-hunt-extension-${kind}-${Date.now()}.json`);
  await fs.writeFile(tracePath, JSON.stringify(payload, null, 2), "utf-8");
  return tracePath;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

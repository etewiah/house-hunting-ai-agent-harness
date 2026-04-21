const FEATURE_KEYWORDS = [
  "parking",
  "garden",
  "garage",
  "walkable",
  "quiet street",
  "balcony",
  "lift",
];

export function extractListingFromHtml(url, html, commuteMinutes = null) {
  const jsonLdObjects = extractJsonLd(html);
  const mergedJsonLd = pickBestJsonLd(jsonLdObjects);
  const pageText = stripTags(removeScriptsAndStyles(html));
  const siteSpecific = extractSiteSpecificListing(url, html, pageText, jsonLdObjects);

  const title = firstNonEmpty(
    siteSpecific.title,
    stringAtPath(mergedJsonLd, ["name"]),
    extractMeta(html, "property=\"og:title\"", "content"),
    extractTitleTag(html),
    "Untitled listing",
  );
  const description = firstNonEmpty(
    siteSpecific.description,
    stringAtPath(mergedJsonLd, ["description"]),
    extractMeta(html, "name=\"description\"", "content"),
    pageText.slice(0, 280).trim(),
    "",
  );
  const price = firstInt(
    siteSpecific.price,
    numberAtPath(mergedJsonLd, ["offers", "price"]),
    numberAtPath(mergedJsonLd, ["offers", 0, "price"]),
    extractCurrencyInt(pageText),
    0,
  );
  const bedrooms = firstInt(
    siteSpecific.bedrooms,
    numberAtPath(mergedJsonLd, ["numberOfRooms"]),
    regexInt(pageText, /(\d+)\s*(?:bed|bedroom)/i),
    0,
  );
  const bathrooms = firstInt(
    siteSpecific.bathrooms,
    regexInt(pageText, /(\d+)\s*(?:bath|bathroom)/i),
    0,
  );
  const canonicalUrl = firstNonEmpty(
    siteSpecific.source_url,
    stringAtPath(mergedJsonLd, ["url"]),
    extractCanonicalUrl(html),
    url,
  );
  const location = firstNonEmpty(
    siteSpecific.location,
    stringAtPath(mergedJsonLd, ["address", "addressLocality"]),
    stringAtPath(mergedJsonLd, ["address", "streetAddress"]),
    inferLocationFromTitle(title),
    inferLocationFromText(pageText),
    "unknown",
  );
  const features = Array.from(new Set([
    ...(siteSpecific.features ?? []),
    ...FEATURE_KEYWORDS.filter((keyword) => new RegExp(`\\b${escapeRegExp(keyword)}\\b`, "i").test(pageText)),
  ])).filter(Boolean);

  const diagnostics = buildExtractionDiagnostics(url, jsonLdObjects, siteSpecific);

  return {
    listing: {
      id: siteSpecific.id || createListingId(canonicalUrl),
      title,
      price,
      bedrooms,
      bathrooms,
      location,
      commute_minutes: commuteMinutes,
      features,
      description,
      source_url: canonicalUrl,
    },
    diagnostics,
  };
}

function extractJsonLd(html) {
  const matches = [...html.matchAll(/<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/gi)];
  const parsed = [];
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

function pickBestJsonLd(items) {
  return items.find((item) => item && typeof item === "object" && (item.offers || item.address || item.name)) ?? {};
}

function extractMeta(html, attrSelector, targetAttr) {
  const regex = new RegExp(`<meta[^>]*${attrSelector}[^>]*${targetAttr}="([^"]*)"[^>]*>`, "i");
  return regex.exec(html)?.[1];
}

function extractTitleTag(html) {
  return stripTags((/<title[^>]*>([\s\S]*?)<\/title>/i.exec(html)?.[1] ?? "")).trim() || undefined;
}

function extractCanonicalUrl(html) {
  return /<link[^>]*rel="canonical"[^>]*href="([^"]+)"[^>]*>/i.exec(html)?.[1];
}

function removeScriptsAndStyles(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ");
}

function stripTags(text) {
  return text.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
}

function decodeHtml(text) {
  return text
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#x2F;/g, "/");
}

function stringAtPath(value, pathParts) {
  let current = value;
  for (const part of pathParts) {
    if (current == null) return undefined;
    current = current[part];
  }
  return typeof current === "string" ? current.trim() || undefined : undefined;
}

function numberAtPath(value, pathParts) {
  let current = value;
  for (const part of pathParts) {
    if (current == null) return undefined;
    current = current[part];
  }
  if (typeof current === "number") return current;
  if (typeof current === "string") return extractCurrencyInt(current) ?? regexInt(current, /(\d+)/);
  return undefined;
}

function extractCurrencyInt(text) {
  const match = text.match(/£\s*([0-9][0-9,]*)/);
  if (!match) return undefined;
  return Number(match[1].replace(/,/g, ""));
}

function regexInt(text, regex) {
  const match = regex.exec(text);
  return match ? Number(match[1]) : undefined;
}

function firstNonEmpty(...values) {
  for (const value of values) {
    if (value && value.trim()) return value.trim();
  }
  return "";
}

function firstInt(...values) {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) return Math.round(value);
  }
  return 0;
}

function inferLocationFromTitle(title) {
  const parts = title.split(/[|,-]/).map((part) => part.trim()).filter(Boolean);
  return parts.length > 1 ? parts[parts.length - 1] : undefined;
}

function inferLocationFromText(text) {
  const match = text.match(/\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b/);
  return match?.[1];
}

function createListingId(rawUrl) {
  try {
    const url = new URL(rawUrl);
    const slug = `${url.hostname}${url.pathname}`.replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    return slug || `listing-${Date.now()}`;
  } catch {
    return `listing-${Date.now()}`;
  }
}

function extractSiteSpecificListing(url, html, pageText, jsonLdObjects) {
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

function extractRightmoveListing(url, html, pageText, jsonLdObjects) {
  const nextData = extractNextData(html);
  const pageModel = extractAssignedJson(html, /window\.PAGE_MODEL\s*=\s*/);
  const propertyData =
    findObject(nextData, (value) => typeof value?.id !== "undefined" && (value?.bedrooms || value?.bathrooms || value?.propertySubType))
    ?? findObject(pageModel, (value) => typeof value?.id !== "undefined" && (value?.bedrooms || value?.bathrooms || value?.propertySubType))
    ?? {};
  const features = normalizeFeatures([
    ...collectStrings(propertyData?.keyFeatures),
    ...collectStrings(findValue(nextData, (value) => Array.isArray(value) && value.some((item) => typeof item === "string" && /parking|garden|garage|balcony|lift/i.test(item))) ?? []),
  ]);
  return {
    id: firstNonEmpty(propertyData?.id != null ? `rightmove-${propertyData.id}` : undefined, createListingId(url)),
    title: firstNonEmpty(propertyData?.headline, propertyData?.displayAddress, stringAtPath(pickBestJsonLd(jsonLdObjects), ["name"])),
    price: firstInt(coerceInt(propertyData?.prices?.primaryPrice), coerceInt(propertyData?.price), extractCurrencyInt(pageText)),
    bedrooms: firstInt(coerceInt(propertyData?.bedrooms), regexInt(pageText, /(\d+)\s*(?:bed|bedroom)/i)),
    bathrooms: firstInt(coerceInt(propertyData?.bathrooms), regexInt(pageText, /(\d+)\s*(?:bath|bathroom)/i)),
    location: firstNonEmpty(propertyData?.displayAddress, propertyData?.address, inferLocationFromTitle(extractTitleTag(html) ?? "")),
    description: firstNonEmpty(propertyData?.summary, propertyData?.description, extractMeta(html, "name=\"description\"", "content")),
    features,
    source_url: firstNonEmpty(propertyData?.url, extractCanonicalUrl(html), url),
  };
}

function extractZooplaListing(url, html, pageText, jsonLdObjects) {
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
    id: firstNonEmpty(listing?.listingId != null ? `zoopla-${listing.listingId}` : undefined, listing?.id != null ? `zoopla-${listing.id}` : undefined, createListingId(url)),
    title: firstNonEmpty(listing?.title, listing?.propertyType, extractTitleTag(html)),
    price: firstInt(coerceInt(listing?.price), coerceInt(listing?.pricing?.value), extractCurrencyInt(pageText)),
    bedrooms: firstInt(coerceInt(listing?.beds), coerceInt(listing?.bedrooms), regexInt(pageText, /(\d+)\s*(?:bed|bedroom)/i)),
    bathrooms: firstInt(coerceInt(listing?.baths), coerceInt(listing?.bathrooms), regexInt(pageText, /(\d+)\s*(?:bath|bathroom)/i)),
    location: firstNonEmpty(listing?.address, listing?.location, listing?.branch?.displayAddress, stringAtPath(pickBestJsonLd(jsonLdObjects), ["address", "addressLocality"])),
    description: firstNonEmpty(listing?.description, extractMeta(html, "name=\"description\"", "content")),
    features,
    source_url: firstNonEmpty(listing?.canonicalUrl, extractCanonicalUrl(html), url),
  };
}

function extractOnTheMarketListing(url, html, pageText, jsonLdObjects) {
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
    id: firstNonEmpty(listing?.id != null ? `onthemarket-${listing.id}` : undefined, listing?.propertyId != null ? `onthemarket-${listing.propertyId}` : undefined, createListingId(url)),
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

function extractNextData(html) {
  return extractScriptJson(html, /<script[^>]*id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/i) ?? {};
}

function extractScriptJson(html, regex) {
  const match = regex.exec(html);
  if (!match) return undefined;
  try {
    return JSON.parse(decodeHtml(match[1]));
  } catch {
    return undefined;
  }
}

function extractAssignedJson(html, prefixRegex) {
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

function findBalancedJsonEnd(text, start) {
  let depth = 0;
  let inString = false;
  let escape = false;
  for (let i = start; i < text.length; i += 1) {
    const char = text[i];
    if (inString) {
      if (escape) escape = false;
      else if (char === "\\") escape = true;
      else if (char === '"') inString = false;
      continue;
    }
    if (char === '"') { inString = true; continue; }
    if (char === "{" || char === "[") depth += 1;
    if (char === "}" || char === "]") {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return -1;
}

function findObject(root, predicate) {
  return findValue(root, (value) => !!value && typeof value === "object" && predicate(value));
}

function findValue(root, predicate) {
  const seen = new Set();
  const stack = [root];
  while (stack.length > 0) {
    const value = stack.pop();
    if (value == null || typeof value !== "object") continue;
    if (seen.has(value)) continue;
    seen.add(value);
    if (predicate(value)) return value;
    if (Array.isArray(value)) for (const item of value) stack.push(item);
    else for (const item of Object.values(value)) stack.push(item);
  }
  return undefined;
}

function collectStrings(value) {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item === "string") return [item];
    if (item && typeof item === "object") return Object.values(item).filter((v) => typeof v === "string");
    return [];
  });
}

function normalizeFeatures(values) {
  const lowered = values.map((value) => value.trim()).filter(Boolean).join(" | ").toLowerCase();
  const synonyms = {
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

function coerceInt(value) {
  if (typeof value === "number" && Number.isFinite(value)) return Math.round(value);
  if (typeof value === "string") return extractCurrencyInt(value) ?? regexInt(value, /(\d+)/);
  return undefined;
}

function buildExtractionDiagnostics(url, jsonLdObjects, siteSpecific) {
  const sourceHints = [];
  const fieldSources = {};
  if (siteSpecific._parser && siteSpecific._parser !== "generic") sourceHints.push(`site:${siteSpecific._parser}`);
  for (const field of ["title", "description", "price", "bedrooms", "bathrooms", "location", "source_url"]) {
    if (siteSpecific[field] !== undefined && siteSpecific[field] !== "") fieldSources[field] = "site_specific";
    else if (jsonLdObjects.length > 0) fieldSources[field] = "json_ld_or_fallback";
    else fieldSources[field] = "text_or_meta";
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

function safeHostname(rawUrl) {
  try {
    return new URL(rawUrl).hostname.replace(/^www\./, "");
  } catch {
    return undefined;
  }
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

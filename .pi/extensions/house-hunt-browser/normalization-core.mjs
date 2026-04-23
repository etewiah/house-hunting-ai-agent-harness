export function normalizeListingInput(listing) {
  return {
    id: String(listing.id ?? ''),
    title: String(listing.title ?? ''),
    price: coerceInt(listing.price) ?? 0,
    bedrooms: coerceInt(listing.bedrooms) ?? 0,
    bathrooms: coerceInt(listing.bathrooms) ?? 0,
    location: String(listing.location ?? ''),
    commute_minutes: listing.commute_minutes == null || listing.commute_minutes === '' ? null : (coerceInt(listing.commute_minutes) ?? null),
    features: coerceStringArray(listing.features),
    description: String(listing.description ?? ''),
    source_url: String(listing.source_url ?? ''),
    image_urls: coerceOptionalStringArray(listing.image_urls),
    external_refs: isRecord(listing.external_refs) ? listing.external_refs : undefined,
  };
}

function coerceInt(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return Math.round(value);
  if (typeof value === 'string') return extractCurrencyInt(value) ?? regexInt(value, /(\d+)/);
  return undefined;
}

function extractCurrencyInt(text) {
  const match = text.match(/£\s*([0-9][0-9,]*)/);
  if (!match) return undefined;
  return Number(match[1].replace(/,/g, ''));
}

function regexInt(text, regex) {
  const match = regex.exec(text);
  return match ? Number(match[1]) : undefined;
}

function coerceStringArray(value) {
  if (value == null || value === '') return [];
  if (Array.isArray(value)) return value.map((item) => String(item));
  return [String(value)];
}

function coerceOptionalStringArray(value) {
  const values = coerceStringArray(value);
  return values.length > 0 ? values : undefined;
}

function isRecord(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

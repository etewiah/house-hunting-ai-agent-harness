const HUB_TO_CITY = {
  'birmingham new street': 'birmingham',
  'birmingham moor street': 'birmingham',
  'birmingham snow hill': 'birmingham',
  'london bridge': 'london',
  'king\'s cross': 'london',
  'kings cross': 'london',
  'manchester piccadilly': 'manchester',
  'bristol temple meads': 'bristol',
};

const WEST_MIDLANDS_CITIES = new Set(['birmingham', 'solihull', 'coventry', 'wolverhampton', 'dudley', 'walsall', 'west bromwich']);

export function estimateCommuteMinutes(origin, destination, mode = 'transit') {
  if (!origin || !destination) return null;

  const normalizedOrigin = normalize(origin);
  const normalizedDestination = normalize(destination);
  if (!normalizedOrigin || !normalizedDestination) return null;

  if (normalizedOrigin.includes(normalizedDestination) || normalizedDestination.includes(normalizedOrigin)) {
    return baseForMode(mode, 12, 18, 45);
  }

  const originCity = resolveCity(normalizedOrigin);
  const destinationCity = resolveCity(normalizedDestination);

  if (originCity && destinationCity && originCity === destinationCity) {
    return baseForMode(mode, 20, 24, 70);
  }

  if (originCity && destinationCity && WEST_MIDLANDS_CITIES.has(originCity) && WEST_MIDLANDS_CITIES.has(destinationCity)) {
    return baseForMode(mode, 28, 38, 999);
  }

  return baseForMode(mode, 35, 55, 999);
}

export function enrichListingsWithCommute(listings, destination, mode = 'transit') {
  if (!destination) return listings;
  return listings.map((listing) => {
    if (listing.commute_minutes != null) return listing;
    const estimate = estimateCommuteMinutes(listing.location, destination, mode);
    if (estimate == null) return listing;
    return {
      ...listing,
      commute_minutes: estimate,
      external_refs: {
        ...(listing.external_refs ?? {}),
        commute_estimation: {
          destination,
          mode,
          source: 'estimated',
          provider: 'house-hunt-browser-heuristic',
        },
      },
    };
  });
}

export function inferCommuteDestinationFromBrief(brief) {
  const lowered = normalize(brief);
  if (!lowered) return null;
  const match = lowered.match(/(?:near|to|commute to|commute near|within \d+ min(?:utes)? of)\s+([a-z][a-z\s']{2,40})/i);
  if (!match) return null;
  return tidyDestination(match[1]);
}

function normalize(value) {
  return String(value ?? '').toLowerCase().replace(/\s+/g, ' ').trim();
}

function tidyDestination(value) {
  return value
    .split(',')[0]
    .replace(/\b(?:under|budget|with|and|need|max)\b.*$/i, '')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function resolveCity(value) {
  for (const [hub, city] of Object.entries(HUB_TO_CITY)) {
    if (value.includes(hub)) return city;
  }
  for (const city of WEST_MIDLANDS_CITIES) {
    if (value.includes(city)) return city;
  }
  for (const city of ['london', 'manchester', 'bristol', 'leeds', 'liverpool', 'edinburgh', 'glasgow']) {
    if (value.includes(city)) return city;
  }
  return null;
}

function baseForMode(mode, transit, driving, walking) {
  if (mode === 'driving') return driving;
  if (mode === 'walking') return walking;
  return transit;
}

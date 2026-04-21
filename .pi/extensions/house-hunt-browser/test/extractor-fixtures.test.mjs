import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { extractListingFromHtml } from '../extractor-core.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixturesDir = path.join(__dirname, 'fixtures');

const cases = [
  {
    name: 'rightmove fixture uses PAGE_MODEL parser',
    file: 'rightmove.html',
    url: 'https://www.rightmove.co.uk/properties/123456789',
    expected: {
      parser: 'rightmove',
      title: 'Station Quarter Flat',
      price: 235000,
      bedrooms: 2,
      bathrooms: 1,
      location: 'Birmingham City Centre',
      features: ['parking', 'balcony'],
      source: 'site_specific',
    },
  },
  {
    name: 'zoopla fixture uses __NEXT_DATA__ parser',
    file: 'zoopla.html',
    url: 'https://www.zoopla.co.uk/for-sale/details/42/',
    expected: {
      parser: 'zoopla',
      title: 'Canal Side Apartment',
      price: 245000,
      bedrooms: 2,
      bathrooms: 2,
      location: 'Birmingham',
      features: ['garden', 'lift'],
      source: 'site_specific',
    },
  },
  {
    name: 'onthemarket fixture uses __NEXT_DATA__ parser with json-ld present',
    file: 'onthemarket.html',
    url: 'https://www.onthemarket.com/details/7/',
    expected: {
      parser: 'onthemarket',
      title: 'Garden View Flat',
      price: 240000,
      bedrooms: 2,
      bathrooms: 1,
      location: 'Edgbaston, Birmingham',
      features: ['parking', 'garden'],
      source: 'site_specific',
      hadJsonLd: true,
    },
  },
];

for (const fixtureCase of cases) {
  test(fixtureCase.name, async () => {
    const html = await readFile(path.join(fixturesDir, fixtureCase.file), 'utf-8');
    const result = extractListingFromHtml(fixtureCase.url, html, null);

    assert.equal(result.diagnostics.parser, fixtureCase.expected.parser);
    assert.equal(result.listing.title, fixtureCase.expected.title);
    assert.equal(result.listing.price, fixtureCase.expected.price);
    assert.equal(result.listing.bedrooms, fixtureCase.expected.bedrooms);
    assert.equal(result.listing.bathrooms, fixtureCase.expected.bathrooms);
    assert.equal(result.listing.location, fixtureCase.expected.location);
    assert.equal(result.diagnostics.fieldSources.title, fixtureCase.expected.source);
    for (const feature of fixtureCase.expected.features) {
      assert.ok(result.listing.features.includes(feature), `expected feature ${feature}`);
    }
    if ('hadJsonLd' in fixtureCase.expected) {
      assert.equal(result.diagnostics.hadJsonLd, fixtureCase.expected.hadJsonLd);
    }
  });
}

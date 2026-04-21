import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { extractListingFromHtml } from '../extractor-core.mjs';
import { fixtureManifest } from './manifest.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixturesDir = path.join(__dirname, 'fixtures');

for (const fixtureCase of fixtureManifest) {
  test(fixtureCase.name, async () => {
    const html = await readFile(path.join(fixturesDir, fixtureCase.file), 'utf-8');
    const result = extractListingFromHtml(fixtureCase.url, html, null);

    if (fixtureCase.expected.allowedParsers) {
      assert.ok(fixtureCase.expected.allowedParsers.includes(result.diagnostics.parser), `expected parser in ${fixtureCase.expected.allowedParsers.join(', ')}`);
    } else {
      assert.equal(result.diagnostics.parser, fixtureCase.expected.parser);
    }

    if (fixtureCase.expected.titleIncludes) {
      assert.ok(result.listing.title.includes(fixtureCase.expected.titleIncludes), `expected title to include ${fixtureCase.expected.titleIncludes}`);
    } else {
      assert.equal(result.listing.title, fixtureCase.expected.title);
    }

    if ('minPrice' in fixtureCase.expected) {
      assert.ok(result.listing.price >= fixtureCase.expected.minPrice, `expected price >= ${fixtureCase.expected.minPrice}`);
    } else {
      assert.equal(result.listing.price, fixtureCase.expected.price);
    }

    assert.equal(result.listing.bedrooms, fixtureCase.expected.bedrooms);
    assert.equal(result.listing.bathrooms, fixtureCase.expected.bathrooms);

    if (fixtureCase.expected.locationIncludes) {
      assert.ok(result.listing.location.includes(fixtureCase.expected.locationIncludes), `expected location to include ${fixtureCase.expected.locationIncludes}`);
    } else {
      assert.equal(result.listing.location, fixtureCase.expected.location);
    }
    for (const [field, source] of Object.entries(fixtureCase.expected.fieldSources ?? {})) {
      assert.equal(result.diagnostics.fieldSources[field], source);
    }
    for (const feature of fixtureCase.expected.features ?? []) {
      assert.ok(result.listing.features.includes(feature), `expected feature ${feature}`);
    }
    for (const featureGroup of fixtureCase.expected.featuresAnyOf ?? []) {
      assert.ok(featureGroup.some((feature) => result.listing.features.includes(feature)), `expected one of features ${featureGroup.join(', ')}`);
    }
    if ('hadJsonLd' in fixtureCase.expected) {
      assert.equal(result.diagnostics.hadJsonLd, fixtureCase.expected.hadJsonLd);
    }
  });
}

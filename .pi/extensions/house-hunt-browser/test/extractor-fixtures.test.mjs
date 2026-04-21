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

    assert.equal(result.diagnostics.parser, fixtureCase.expected.parser);
    assert.equal(result.listing.title, fixtureCase.expected.title);
    assert.equal(result.listing.price, fixtureCase.expected.price);
    assert.equal(result.listing.bedrooms, fixtureCase.expected.bedrooms);
    assert.equal(result.listing.bathrooms, fixtureCase.expected.bathrooms);
    assert.equal(result.listing.location, fixtureCase.expected.location);
    for (const [field, source] of Object.entries(fixtureCase.expected.fieldSources ?? {})) {
      assert.equal(result.diagnostics.fieldSources[field], source);
    }
    for (const feature of fixtureCase.expected.features) {
      assert.ok(result.listing.features.includes(feature), `expected feature ${feature}`);
    }
    if ('hadJsonLd' in fixtureCase.expected) {
      assert.equal(result.diagnostics.hadJsonLd, fixtureCase.expected.hadJsonLd);
    }
  });
}

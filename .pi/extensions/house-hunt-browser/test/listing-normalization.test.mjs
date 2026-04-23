import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeListingInput } from '../normalization-core.mjs';

test('normalizeListingInput accepts browser-style numeric strings', () => {
  const normalized = normalizeListingInput({
    id: 'listing-1',
    title: 'Example home',
    price: '£250,000',
    bedrooms: '3 bedrooms',
    bathrooms: '1 bathroom',
    location: 'Birmingham',
    commute_minutes: '22 min',
    features: 'parking',
    description: 'Near station',
    source_url: 'https://example.com/listing',
    image_urls: 'https://example.com/a.jpg',
    external_refs: { extraction_quality_score: 80 },
  });

  assert.equal(normalized.price, 250000);
  assert.equal(normalized.bedrooms, 3);
  assert.equal(normalized.bathrooms, 1);
  assert.equal(normalized.commute_minutes, 22);
  assert.deepEqual(normalized.features, ['parking']);
  assert.deepEqual(normalized.image_urls, ['https://example.com/a.jpg']);
  assert.equal(normalized.external_refs.extraction_quality_score, 80);
});

test('normalizeListingInput drops invalid optional structures', () => {
  const normalized = normalizeListingInput({
    id: 'listing-2',
    title: 'Example home',
    price: null,
    bedrooms: '',
    bathrooms: undefined,
    location: 'Birmingham',
    commute_minutes: '',
    features: null,
    description: '',
    source_url: 'https://example.com/listing',
    image_urls: null,
    external_refs: 'bad',
  });

  assert.equal(normalized.price, 0);
  assert.equal(normalized.bedrooms, 0);
  assert.equal(normalized.bathrooms, 0);
  assert.equal(normalized.commute_minutes, null);
  assert.deepEqual(normalized.features, []);
  assert.equal(normalized.image_urls, undefined);
  assert.equal(normalized.external_refs, undefined);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { estimateCommuteMinutes, enrichListingsWithCommute, inferCommuteDestinationFromBrief } from '../commute-core.mjs';

test('estimate commute prefers closely matching journeys', () => {
  assert.equal(estimateCommuteMinutes('Birmingham', 'Birmingham New Street'), 12);
});

test('estimate commute distinguishes farther cities', () => {
  assert.equal(estimateCommuteMinutes('Manchester', 'Birmingham New Street'), 35);
});

test('enrich listings fills missing commute and preserves existing commute', () => {
  const listings = [
    { id: 'a', title: 'A', price: 1, bedrooms: 1, bathrooms: 1, location: 'Birmingham', commute_minutes: null, features: [], description: '', source_url: 'https://a' },
    { id: 'b', title: 'B', price: 1, bedrooms: 1, bathrooms: 1, location: 'Birmingham', commute_minutes: 14, features: [], description: '', source_url: 'https://b' },
  ];
  const enriched = enrichListingsWithCommute(listings, 'Birmingham New Street');
  assert.equal(enriched[0].commute_minutes, 12);
  assert.equal(enriched[1].commute_minutes, 14);
  assert.equal(enriched[0].external_refs.commute_estimation.provider, 'house-hunt-browser-heuristic');
});

test('infer commute destination from brief', () => {
  assert.equal(inferCommuteDestinationFromBrief('2-bed flat near Birmingham New Street, under £250k'), 'Birmingham New Street');
});

import { extractListingFromHtml } from './extractor-core.mjs';
import { readFileSync } from 'fs';

const html = readFileSync('./test/fixtures/rightmove_live_ashton.html', 'utf-8');
try {
  const result = extractListingFromHtml('https://www.rightmove.co.uk/properties/173906975', html, null);
  console.log(JSON.stringify(result, null, 2));
} catch(e) {
  console.error(e.stack);
}

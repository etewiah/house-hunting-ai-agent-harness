import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const html = readFileSync(path.join(__dirname, 'test/fixtures/rightmove_live_ashton.html'), 'utf-8');

function extractNextData(h) {
  const m = /<script[^>]*id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/i.exec(h);
  if (!m) return {};
  try { return JSON.parse(m[1]); } catch { return {}; }
}
function extractAssignedJson(h, pfx) {
  const s = pfx.exec(h);
  if (!s) return undefined;
  const from = s.index + s[0].length;
  let d=0,inStr=false,esc=false;
  for(let i=from;i<h.length;i++){const c=h[i];if(inStr){if(esc)esc=false;else if(c==='\\')esc=true;else if(c==='"')inStr=false;continue;}if(c==='"'){inStr=true;continue;}if(c==='{'||c==='[')d++;if(c==='}'||c===']'){d--;if(d===0){try{return JSON.parse(h.slice(from,i+1));}catch{return undefined;}}}}return undefined;
}
function findObject(root, pred) {
  const seen=new Set(),stack=[root];
  while(stack.length){const v=stack.pop();if(v==null||typeof v!=='object')continue;if(seen.has(v))continue;seen.add(v);if(pred(v))return v;if(Array.isArray(v)){for(const i of v)stack.push(i);}else{for(const i of Object.values(v))stack.push(i);}}return undefined;
}

const nextData = extractNextData(html);
const pageModel = extractAssignedJson(html, /window\.PAGE_MODEL\s*=\s*/);
const pd = findObject(nextData, v => typeof v?.id !== 'undefined' && (v?.bedrooms || v?.bathrooms || v?.propertySubType))
  ?? findObject(pageModel, v => typeof v?.id !== 'undefined' && (v?.bedrooms || v?.bathrooms || v?.propertySubType))
  ?? {};

const check = (label, val) =>
  console.log(`${label}: [${typeof val}] ${JSON.stringify(val)?.slice(0, 120) ?? 'undefined'}`);

check('displayAddress', pd?.displayAddress);
check('address', pd?.address);
check('headline', pd?.headline);
check('url', pd?.url);
check('summary', pd?.summary);
check('description', pd?.description);
check('id', pd?.id);
check('bedrooms', pd?.bedrooms);
check('bathrooms', pd?.bathrooms);
check('prices.primaryPrice', pd?.prices?.primaryPrice);
check('price', pd?.price);

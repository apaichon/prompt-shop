const {chromium}=require('@playwright/test');
(async()=>{const browser=await chromium.launch();
const page=await browser.newPage({viewport:{width:1440,height:1050}});
const faults=[];page.on('pageerror',e=>faults.push(e.message));
await page.goto('http://localhost:8080');await page.locator('.catalog-browser .product-card').first().waitFor();
await page.screenshot({path:'docs/design/assets/products/desktop-catalog.png',fullPage:true});
await page.locator('.catalog-browser .route-button').first().click();await page.locator('.shelf-facing.selected').waitFor();
await page.screenshot({path:'docs/design/assets/products/desktop-shelf.png',fullPage:true});
await page.setViewportSize({width:390,height:844});
await page.screenshot({path:'docs/design/assets/products/mobile-shelf.png',fullPage:true});
const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
const response=await page.request.get('http://localhost:8080/api/products?page_size=24');const initial=await response.json();
const ids=[];for(let p=1;p<=Math.ceil(initial.total/24);p++){const r=await page.request.get('http://localhost:8080/api/products?page_size=24&page='+p);ids.push(...(await r.json()).products.map(x=>x.id));}
const images=require('../../src/lib/product-images.json');
console.log(JSON.stringify({published:initial.total,unique:new Set(ids).size,all_images:ids.every(id=>images[id]),no_inactive:!ids.some(id=>id.startsWith('example-')),shelf_count:await page.locator('.shelf-facing').count(),mobile_overflow:overflow,page_errors:faults}));
await browser.close();if(overflow||faults.length||initial.total!==120||new Set(ids).size!==120)process.exitCode=1;})();

import {test,expect,type Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const password='task9-test-password-only';
async function login(page:Page){await page.goto('/backoffice');await page.getByLabel('Maintainer password').fill(password);await page.getByRole('button',{name:'Log in',exact:true}).click();await expect(page.getByRole('button',{name:'+ New item',exact:true})).toBeVisible()}
async function waitWrite(){await new Promise(resolve=>setTimeout(resolve,3100))}

test('real HTTPS cookie, CSRF, CRUD, pagination, published-edit draft and logout',async({page,context})=>{
 await login(page);
 const cookie=(await context.cookies()).find(c=>c.name==='__Host-maintainer')!;
 expect(cookie).toMatchObject({secure:true,httpOnly:true,sameSite:'Strict',path:'/'});
 expect(await page.evaluate(()=>document.cookie)).not.toContain('__Host-maintainer');
 await page.getByRole('button',{name:'Next →',exact:true}).click();await expect(page.getByText('Page 2',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'← Previous',exact:true}).click();
 await page.getByRole('button',{name:'+ New item',exact:true}).click();await expect(page.getByLabel('Item name',{exact:true})).toBeFocused();
 await page.getByLabel('Item ID',{exact:true}).fill('browser-qa-item');await page.getByLabel('Item name',{exact:true}).fill('Browser QA item');await page.getByLabel('Category',{exact:true}).fill('Pantry');await page.getByLabel('Shelf location',{exact:true}).selectOption('a01-s01');await page.getByLabel('English search aliases').fill('browser qa item');
 await page.getByRole('button',{name:'Save as draft',exact:true}).click();await expect(page.getByRole('status')).toContainText('Saved as draft');
 await page.getByRole('button',{name:'Publish item',exact:true}).click();await expect(page.getByRole('status')).toContainText('Published.');
 await page.getByLabel('Item name',{exact:true}).fill('Browser QA updated');await expect(page.getByRole('button',{name:'Publish item',exact:true})).toBeDisabled();
 await expect(page.getByText('Saving changes hides this item from shoppers until you publish it again.')).toBeVisible();
 await waitWrite();await page.getByRole('button',{name:'Save as draft',exact:true}).click();await expect(page.getByRole('status')).toContainText('Saved as draft');
 await expect(page.getByRole('button',{name:'Publish item',exact:true})).toBeEnabled();
 await waitWrite();await page.getByRole('button',{name:'Publish item',exact:true}).click();await expect(page.getByRole('status')).toContainText('Published.');
 await waitWrite();await page.getByRole('button',{name:'Archive item',exact:true}).click();await expect(page.getByRole('status')).toContainText('Archived.');
 await page.reload();await expect(page.getByRole('button',{name:'+ New item',exact:true})).toBeVisible();
 // Same cookie works after page reload, and data is served from PostgreSQL.
 await page.getByLabel('Search catalog',{exact:true}).fill('browser qa updated');await page.getByRole('button',{name:'Filter',exact:true}).click();await expect(page.getByRole('button',{name:'Edit Browser QA updated',exact:true})).toBeVisible();
 const noCsrf=await page.request.post('/api/backoffice/products/browser-qa-item/publish',{headers:{Origin:'https://127.0.0.1:4194'},data:{expected_version:5}});expect(noCsrf.status()).toBe(403);
 await waitWrite();await page.getByRole('button',{name:'Log out',exact:true}).click();await expect(page.getByLabel('Maintainer password')).toBeVisible();
 expect((await page.request.get('/api/backoffice/products')).status()).toBe(401);
 const replay=await page.request.get('/api/backoffice/products',{headers:{Cookie:`${cookie.name}=${cookie.value}`}});expect(replay.status()).toBe(401);
});

for(const width of [320,768,1280])test(`real backoffice keyboard and accessibility at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:900});
 // Respect the real login bucket between browser contexts.
 await new Promise(resolve=>setTimeout(resolve,12500));await login(page);
 await page.getByLabel('Search catalog',{exact:true}).fill('whole milk');await page.getByLabel('Search catalog',{exact:true}).press('Enter');
 const item=page.getByRole('button',{name:'Edit Whole milk 1 L',exact:true});await item.focus();await page.keyboard.press('Enter');await expect(page.getByLabel('Item name',{exact:true})).toBeFocused();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
 await page.screenshot({path:`test-results/backoffice-${width}.png`,fullPage:true});
});

test('server conflict keeps the edit until explicit latest-version reload',async({page})=>{
 await new Promise(resolve=>setTimeout(resolve,12500));await login(page);
 await page.getByLabel('Search catalog',{exact:true}).fill('whole milk');await page.getByRole('button',{name:'Filter',exact:true}).click();await page.getByRole('button',{name:'Edit Whole milk 1 L',exact:true}).click();
 const session=await (await page.request.get('/api/backoffice/session')).json();
 const latest=(await (await page.request.get('/api/backoffice/products?q=whole%20milk')).json()).items[0];
 const changed=await page.request.put(`/api/backoffice/products/${latest.id}`,{headers:{Origin:'https://127.0.0.1:4194','X-CSRF-Token':session.csrf_token},data:{name:'Other editor milk',category:latest.category,shelf_id:latest.shelf_id,aliases:latest.aliases,expected_version:latest.version}});expect(changed.status()).toBe(200);
 await page.getByLabel('Item name',{exact:true}).fill('My unsaved milk');await page.getByRole('button',{name:'Save as draft',exact:true}).click();await expect(page.getByRole('alert')).toContainText('A newer version');await expect(page.getByLabel('Item name',{exact:true})).toHaveValue('My unsaved milk');
 await page.getByRole('button',{name:'Replace edit with latest version',exact:true}).click();await expect(page.getByLabel('Item name',{exact:true})).toHaveValue('Other editor milk');
});

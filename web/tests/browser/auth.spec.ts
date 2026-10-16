import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import map from '../fixtures/store-map.json' with {type:'json'};
for(const role of ['shopper','admin'])test(`shared sign-in and ${role} scope`,async({page})=>{
 let signed=false,protectedCalls=0,logouts=0;
 await page.route('**/api/**',async r=>{
  const path=new URL(r.request().url()).pathname,method=r.request().method();
  if(path==='/api/auth/session'){
   if(method==='POST'){const body=r.request().postDataJSON();if(body.password!=='fixture-password')return r.fulfill({status:401,json:{}});signed=true;}
   if(method==='DELETE'){expect(r.request().headers()['x-csrf-token']).toBe('fixture-csrf');signed=false;logouts++;return r.fulfill({status:204});}
   return r.fulfill({status:signed?200:401,json:signed?{enabled:true,username:role==='admin'?'demo01':'demo02',role,expires_at:new Date(Date.now()+3600000).toISOString(),csrf_token:'fixture-csrf'}:{}});
  }
  protectedCalls++;expect(signed).toBe(true);
  if(path==='/api/store-map')return r.fulfill({json:map});
  if(path==='/api/products')return r.fulfill({json:{catalog_version:1,products:[],total:0,page:1,page_size:12,categories:[]}});
  if(path==='/api/backoffice/session')return r.fulfill({json:{csrf_token:'fixture-csrf',expires_at:new Date(Date.now()+3600000).toISOString()}});
  if(path==='/api/backoffice/products')return r.fulfill({json:{items:[],next_cursor:null}});
  if(path==='/api/backoffice/shelves')return r.fulfill({json:{shelves:[]}});
  throw new Error(path);
 });
 await page.goto('/');await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();expect(protectedCalls).toBe(0);
 await page.getByLabel('Username',{exact:true}).fill(role==='admin'?'demo01':'demo02');await page.getByLabel('Password',{exact:true}).fill('wrong');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('status')).toContainText('incorrect');expect(protectedCalls).toBe(0);
 await page.getByLabel('Password',{exact:true}).fill('fixture-password');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('button',{name:'Sign out',exact:true})).toBeVisible();await expect(page.getByRole('img',{name:/floor map/i})).toBeVisible();
 await page.goto('/backoffice');if(role==='shopper')await expect(page.getByRole('heading',{name:'Administrator access required'})).toBeVisible();else await expect(page.locator('main')).not.toContainText('Administrator access required');
 await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();expect(logouts).toBe(1);
 await page.setViewportSize({width:320,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
});

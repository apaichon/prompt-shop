import {describe,it,expect,vi} from 'vitest';
import {get} from 'svelte/store';
import {BackofficeApi,BackofficeError,product as productSchema} from '../../src/routes/backoffice/api';
import {Backoffice} from '../../src/routes/backoffice/model';
import rawProduct from '../fixtures/admin-product.json';
const product=productSchema.parse(rawProduct);
const session={expires_at:new Date(Date.now()+28800000).toISOString(),csrf_token:'csrf-test'};
const response=(body:unknown,status=200)=>new Response(status===204?null:JSON.stringify(body),{status});
const deferred=<T>()=>{let resolve!:(v:T)=>void;const promise=new Promise<T>(r=>resolve=r);return{promise,resolve}};
const fixture=(mutate?:(path:string)=>Response)=>new BackofficeApi(vi.fn(async(path)=>{
 if(String(path).endsWith('/session'))return response(session);
 if(String(path).startsWith('/api/backoffice/products?'))return response({items:[product],next_cursor:null});
 if(String(path).endsWith('/shelves'))return response({items:[{id:'a02-s03',label:'Shelf 3',aisle:{id:'a02',label:'Aisle 2'},mapped:true}]});
 return mutate?.(String(path))??response({...product,state:'draft',version:2});
}));
describe('backoffice controlled edits and API boundaries',()=>{
 it('uses same-origin cookie auth and in-memory CSRF; does not accept extra product fields',async()=>{
  const fetcher=vi.fn(async()=>response({...product,provider_key:'secret'}));const api=new BackofficeApi(fetcher);api.csrf='csrf-test';
  await expect(api.save({name:'Milk',category:'Dairy',shelf_id:'a02-s03',aliases:[]},product.id,1)).rejects.toMatchObject({code:'INVALID_RESPONSE'});
  expect(fetcher.mock.calls[0]).toMatchObject(['/api/backoffice/products/milk-whole-1l',{method:'PUT',credentials:'same-origin',headers:{'X-CSRF-Token':'csrf-test'}}]);
 });
 it('retains an unsaved edit on expiry and blocks publication until saved',async()=>{
  const api=fixture();const office=new Backoffice(api);await office.init();office.edit(product);office.update({...get(office).draft!,name:'Unsaved milk'});
  await office.transition('publish');expect(get(office).message).toContain('Save your changes');
  api.session=vi.fn(async()=>{throw new BackofficeError('AUTH_REQUIRED')});await office.init();expect(get(office).phase).toBe('anonymous');expect(get(office).draft?.name).toBe('Unsaved milk');expect(api.csrf).toBe('');
  await office.login('password');expect(get(office).draft?.name).toBe('Unsaved milk');office.destroy();
 });
 it('keeps the old version and unsaved content on conflict, then explicitly reloads',async()=>{
  const office=new Backoffice(fixture(()=>response({error:{code:'VERSION_CONFLICT'}},409)));await office.init();office.edit(product);office.update({...get(office).draft!,name:'Unsaved milk'});await office.save();
  expect(get(office).conflict).toBe(true);expect(get(office).draft?.name).toBe('Unsaved milk');expect(get(office).draft?.version).toBe(1);
  await office.reloadLatest();expect(get(office).conflict).toBe(false);expect(get(office).draft?.name).toBe(product.name);office.destroy();
 });
 it('logout clears editing data and late list responses cannot restore the session',async()=>{
  const api=fixture();api.logout=vi.fn(async()=>{api.csrf=''});const office=new Backoffice(api);await office.init();office.edit(product);const late=deferred<{items:typeof product[];next_cursor:null}>();api.list=vi.fn(()=>late.promise) as any;
  const pending=office.load();await office.logout();late.resolve({items:[product],next_cursor:null});await pending;
  expect(get(office).phase).toBe('anonymous');expect(get(office).draft).toBeNull();expect(get(office).items).toHaveLength(0);office.destroy();
 });
 it('shows only the latest filter results despite reordered replies',async()=>{
  const api=fixture();const office=new Backoffice(api);await office.init();const late=deferred<any>();api.list=vi.fn((q)=>q==='old'?late.promise:Promise.resolve({items:[],next_cursor:null}));
  const pending=office.load('',[],{q:'old',state:''});await office.load('',[],{q:'new',state:''});late.resolve({items:[product],next_cursor:null});await pending;expect(get(office).q).toBe('new');expect(get(office).items).toHaveLength(0);office.destroy();
 });
});

it('explicit logout clears edits even if the server session already expired',async()=>{
 const api=fixture();const office=new Backoffice(api);await office.init();office.edit(product);
 api.logout=vi.fn(async()=>{throw new BackofficeError('AUTH_REQUIRED')});await office.logout();
 expect(get(office).phase).toBe('anonymous');expect(get(office).draft).toBeNull();expect(api.csrf).toBe('');office.destroy();
});

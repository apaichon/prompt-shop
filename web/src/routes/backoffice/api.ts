import { z } from 'zod';
const id = z.string().regex(/^[a-z0-9-]{1,64}$/);
export const alias = z.object({ language: z.enum(['en-US','th-TH','zh-CN','ja-JP']), text: z.string().min(1).max(120) }).strict();
export const product = z.object({ id, name: z.string().min(1).max(120), category: z.string().min(1).max(80), shelf_id: id,
  aliases: z.array(alias).max(20), state: z.enum(['draft','published','archived']), version: z.number().int().positive().max(Number.MAX_SAFE_INTEGER), updated_at: z.iso.datetime({offset:true}) }).strict();
export const shelf = z.object({ id, label:z.string().min(1).max(80), aisle:z.object({id,label:z.string().min(1).max(80)}).strict(),mapped:z.boolean() }).strict();
const session = z.object({expires_at:z.iso.datetime({offset:true}),csrf_token:z.string().min(1).max(128)}).strict();
const page = z.object({items:z.array(product).max(50),next_cursor:z.string().max(1600).nullable()}).strict();
const shelves = z.object({items:z.array(shelf).max(10000)}).strict();
export type Product = z.infer<typeof product>;export type Shelf=z.infer<typeof shelf>;export type Session=z.infer<typeof session>;
export type Content={name:string;category:string;shelf_id:string;aliases:z.infer<typeof alias>[]};
export class BackofficeError extends Error {constructor(public code:string,public retryAfter=0){super(code)}}
export const messages:Record<string,string>={AUTH_REQUIRED:'Your session ended. Log in again to continue; your unsaved edit is kept here.',FORBIDDEN:'This change could not be verified. Reload and log in again.',VERSION_CONFLICT:'This product changed since you opened it. Your edit is kept. Reload the latest version and review your changes.',VALIDATION_FAILED:'Check the product fields, aliases and shelf. Nothing was saved.',RATE_LIMITED:'Please wait before trying again.',DEPENDENCY_UNAVAILABLE:'The catalog is temporarily unavailable. Your edit is kept; try again.',INVALID_RESPONSE:'The catalog returned an incomplete response. Reload and try again.'};
export const errorMessage=(e:unknown)=>messages[e instanceof BackofficeError?e.code:'DEPENDENCY_UNAVAILABLE']??messages.DEPENDENCY_UNAVAILABLE;
export class BackofficeApi {
  csrf='';
  constructor(private fetcher:typeof fetch=(...args)=>fetch(...args)){}
  async request<T>(path:string,schema:z.ZodType<T>|null,method='GET',body?:unknown):Promise<T>{
    let response:Response;
    try{response=await this.fetcher(path,{method,credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000),headers:{Accept:'application/json',...(body!==undefined?{'Content-Type':'application/json'}:{}),...(method!=='GET'&&this.csrf?{'X-CSRF-Token':this.csrf}:{})},body:body===undefined?undefined:JSON.stringify(body)})}catch{throw new BackofficeError('DEPENDENCY_UNAVAILABLE')}
    if(!response.ok){let value:any;try{value=await response.json()}catch{};const code=typeof value?.error?.code==='string'?value.error.code:'DEPENDENCY_UNAVAILABLE';if(code==='AUTH_REQUIRED'){this.csrf='';if(typeof window!=='undefined')window.dispatchEvent(new Event('shop-auth-required'));}const delay=Number(response.headers.get('Retry-After'));throw new BackofficeError(code,Number.isFinite(delay)?Math.min(3600,Math.max(0,delay)):0)}
    if(!schema){if(response.status!==204)throw new BackofficeError('INVALID_RESPONSE');return undefined as T}
    const raw=await response.text();if(raw.length>1000000)throw new BackofficeError('INVALID_RESPONSE');let value;try{value=JSON.parse(raw)}catch{throw new BackofficeError('INVALID_RESPONSE')}
    const parsed=schema.safeParse(value);if(!parsed.success)throw new BackofficeError('INVALID_RESPONSE');return parsed.data;
  }
  async session(){const s=await this.request('/api/backoffice/session',session);this.csrf=s.csrf_token;return s}
  async login(password:string){const s=await this.request('/api/backoffice/session',session,'POST',{password});this.csrf=s.csrf_token;return s}
  async logout(){await this.request('/api/backoffice/session',null,'DELETE');this.csrf='';if(typeof window!=='undefined')window.dispatchEvent(new Event('shop-auth-required'))}
  list(q='',state='',cursor=''){return this.request('/api/backoffice/products?'+new URLSearchParams({q,state,cursor}),page)}
  shelves(){return this.request('/api/backoffice/shelves',shelves)}
  save(content:Content,id:string,expected_version:number|null){return this.request('/api/backoffice/products'+(expected_version===null?'':'/'+encodeURIComponent(id)),product,expected_version===null?'POST':'PUT',expected_version===null?{id,...content}:{...content,expected_version})}
  transition(p:Product,action:'publish'|'archive'){return this.request(`/api/backoffice/products/${encodeURIComponent(p.id)}/${action}`,product,'POST',{expected_version:p.version})}
}

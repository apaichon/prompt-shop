// Credentials stay in the local browser request context; never write a trace or HAR.
const fs=require('node:fs');
async function signIn(page){
 const state=await page.request.get(new URL('/api/auth/session',page.url()).href);
 if(state.status()===200)return;
 if(state.status()!==401)throw new Error('Native auth status unavailable');
 const file=process.env.NATIVE_ACCOUNTS_FILE;if(!file)throw new Error('Set NATIVE_ACCOUNTS_FILE to the private demo credential handout');
 const username=process.env.NATIVE_USERNAME||'demo02';
 const line=fs.readFileSync(file,'utf8').split(/\r?\n/).find(l=>l.startsWith(username+'  '));if(!line)throw new Error('Native test account unavailable');
 const password=line.trim().split(/\s+/)[1];
 const result=await page.request.post(new URL('/api/auth/session',page.url()).href,{headers:{Origin:new URL(page.url()).origin},data:{username,password}});
 if(result.status()!==200)throw new Error('Native sign-in failed');
 await page.reload();
}
module.exports={signIn};

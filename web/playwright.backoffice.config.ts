import {defineConfig} from '@playwright/test';
export default defineConfig({
 testDir:'./tests/backoffice',workers:1,retries:0,timeout:60000,reporter:[['list']],
 use:{baseURL:'https://127.0.0.1:4194',browserName:'chromium',viewport:{width:1280,height:900},ignoreHTTPSErrors:true,trace:'off',screenshot:'off'},
 webServer:{command:'rtk proxy env -u GOROOT /opt/homebrew/bin/go run ./internal/backoffice/cmd/fixture-server',cwd:'..',url:'https://127.0.0.1:4194/healthz',ignoreHTTPSErrors:true,reuseExistingServer:false,timeout:90000}
});

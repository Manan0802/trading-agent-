import { chromium } from 'playwright'
const API='http://127.0.0.1:8000', APP='http://localhost:5173'
const EMAIL=`s+${Date.now()}@example.com`, PW='screenshot-account-pw'
await fetch(`${API}/api/v1/auth/register`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:EMAIL,password:PW,name:'S',phone:'+919000000777'})})
const r=await fetch(`${API}/api/v1/auth/jwt/login`,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({username:EMAIL,password:PW})})
const {access_token}=await r.json()
const b=await chromium.launch()
const ctx=await b.newContext({viewport:{width:1440,height:1100},deviceScaleFactor:2,colorScheme:'dark'})
await ctx.addInitScript(([j])=>{localStorage.setItem('nextrade-theme','dark');localStorage.setItem('nextrade_token',j)},[access_token])
const p=await ctx.newPage()
const errs=[]; p.on('pageerror',e=>errs.push(String(e))); p.on('console',m=>m.type()==='error'&&errs.push(m.text()))
await p.goto(`${APP}/research`,{waitUntil:'networkidle'})
await p.getByRole('tab',{name:'Stocks'}).click()
await p.waitForTimeout(1500)
await p.getByRole('button',{name:/ADANIENT/}).first().click()
await p.waitForTimeout(6000)
await p.screenshot({path:'/tmp/stock-score.png',fullPage:true})
if(errs.length) console.log('ERRORS:',errs.slice(0,3))
await b.close(); console.log('done')

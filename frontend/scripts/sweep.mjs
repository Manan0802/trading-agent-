/**
 * Loads every page in both themes and fails on anything the browser complains
 * about: uncaught errors, console errors, or an API response of 400 or worse.
 *
 *   node scripts/sweep.mjs            with a seeded account
 *   node scripts/sweep.mjs --empty    as a brand-new user with no data
 *
 * The empty run is the one worth keeping honest: every user starts there, and
 * it is the state least likely to be looked at by hand.
 */
import { chromium } from 'playwright'
// 8000 and 8010 are other projects on this machine. A wrong default here does
// not error -- it authenticates against a different app and then reports on it.
const API=process.env.API_URL ?? 'http://127.0.0.1:8020', APP=process.env.APP_URL ?? 'http://localhost:5173'
const EMAIL=`sw+${Date.now()}@example.com`, PW='screenshot-account-pw'
await fetch(`${API}/api/v1/auth/register`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:EMAIL,password:PW,name:'Sw',phone:'+919000000333'})})
const {access_token}=await (await fetch(`${API}/api/v1/auth/jwt/login`,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({username:EMAIL,password:PW})})).json()
const auth={'Content-Type':'application/json',Authorization:`Bearer ${access_token}`}
const seed = process.argv.includes('--empty') ? null : await (async () => {
  const goal = await (await fetch(`${API}/api/v1/goals`,{method:'POST',headers:auth,body:JSON.stringify({goal_type:'education',goal_name:"Daughter's college",target_amount:4000000,current_savings:250000,target_date:'2041-06-01',years:15,risk_profile:'moderate'})})).json()
  const h = await (await fetch(`${API}/api/v1/portfolio/holdings`,{method:'POST',headers:auth,body:JSON.stringify({asset_type:'MF',identifier:'118955',name:'HDFC Flexi Cap Fund - Growth Option - Regular Plan',category:'Flexi Cap'})})).json()
  for (let i=0;i<10;i++) {
    const d=new Date(Date.UTC(2023,i,5))
    await fetch(`${API}/api/v1/portfolio/holdings/${h.id}/transactions`,{method:'POST',headers:auth,body:JSON.stringify({txn_type:'BUY',txn_date:d.toISOString().slice(0,10),units:15,price:1400})})
  }
  await fetch(`${API}/api/v1/profile`,{method:'PATCH',headers:auth,body:JSON.stringify({annual_income:1500000,basic_salary:600000,years_to_goal:15})})
  return goal
})()
const b=await chromium.launch()
let bad=0
for (const theme of ['dark','light']) {
  const ctx=await b.newContext({viewport:{width:1440,height:1000},colorScheme:theme})
  await ctx.addInitScript(([t,j])=>{localStorage.setItem('nextrade-theme',t);localStorage.setItem('nextrade_token',j)},[theme,access_token])
  for (const [name,path] of [['portfolio','/portfolio'],['research','/research'],['screener','/screener'],['screener-all','/screener?view=all'],['profile','/profile'],['goals','/goals'],['goal-new','/goals/new'],...(seed ? [['goal',`/goals/${seed.id}`]] : []),['login','/login']]) {
    const p=await ctx.newPage(); const errs=[]
    p.on('pageerror',e=>errs.push('PAGEERROR '+String(e).slice(0,120)))
    p.on('console',m=>m.type()==='error'&&errs.push('CONSOLE '+m.text().slice(0,120)))
    p.on('response',r=>{ if(r.url().includes('/api/') && r.status()>=400 && r.status()!==401) errs.push(`HTTP ${r.status()} ${r.url().split('/api/v1')[1]?.slice(0,60)}`) })
    await p.goto(`${APP}${path}`,{waitUntil:'networkidle'}); await p.waitForTimeout(9000)
    if(errs.length){ bad++; console.log(`\n${theme}/${name}:`); errs.slice(0,4).forEach(e=>console.log('   '+e)) }
    await p.close()
  }
  await ctx.close()
}
await b.close()
console.log(bad? `\n${bad} page-theme combos with errors` : '\nall pages clean in both themes')

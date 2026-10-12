'use strict';
// Normal headed browser only. Never read request headers, cookies or storage.
const fs = require('node:fs');
const path = require('node:path');
const CATEGORIES = {1:'Yoga Classes',2:'Fitness Classes',4:'Events',5:'All Climbing Lessons',8:'Top Rope Lesson',9:'Rock Climbing Basics',10:'Lead Climbing Lesson',11:'Bouldering Basics',16:'Intro to Kilter Board'};
const IDS = Object.keys(CATEGORIES).map(Number);
const SCOPE = {locationId:2,categoryIds:IDS,timeZone:'America/Chicago'};
const URL = 'https://www.cruxclimbingcenter.com/central-austin/calendar/';
let phase='initial';
class SourceError extends Error { constructor(code){super(code);this.code=code;} }
function requireThat(condition,code='schema_error'){if(!condition)throw new SourceError(code);}
function instant(value){requireThat(typeof value==='string'&&/(Z|[+-]\d{2}:\d{2})$/.test(value)&&Number.isFinite(Date.parse(value)));return new Date(value).toISOString();}
function normalize(b){
 requireThat(Number.isSafeInteger(b.id)&&b.id>0&&Number.isSafeInteger(b.eventId)&&b.eventId>0);
 requireThat(b.locationId===2&&b.timeZone===SCOPE.timeZone&&b.event?.timeZone===SCOPE.timeZone);
 requireThat(typeof b.name==='string'&&b.name.trim().length>0&&b.name.length<=1000);
 requireThat((b.isAllDay===false||b.isAllDay===0)&&Array.isArray(b.event.activities)&&b.event.activities.some(a=>IDS.includes(a.id)));
 requireThat(['active','cancelled','canceled'].includes(b.status));
 // Sold-out is availability, not cancellation. ticketsRemaining never sets status.
 return {id:b.id,eventId:b.eventId,title:b.name,start:instant(b.startDT),end:instant(b.endDT),status:b.status==='active'?'active':'cancelled',timeZone:b.timeZone};
}
function selected(u){
 const ids=u.searchParams.getAll('categoryId').flatMap(s=>s.split(',').map(Number)).sort((a,b)=>a-b);
 return u.searchParams.get('locationId')==='2'&&JSON.stringify(ids)===JSON.stringify(IDS);
}
class Pages {
 constructor(){this.pages=new Map();this.window=null;this.totals=null;}
 add(u,data){
  if(!selected(u))return;
  const p=data.pagination;
  requireThat(p&&['page','pageSize','rowCount','pageCount'].every(k=>Number.isSafeInteger(p[k])));
  requireThat(p.pageSize===50&&p.pageCount>=1&&p.pageCount<=100&&p.page>=1&&p.page<=p.pageCount&&p.rowCount>0,'unexpected_empty');
  requireThat(Number(u.searchParams.get('page'))===p.page&&Number(u.searchParams.get('pageSize'))===p.pageSize);
  requireThat(Array.isArray(data.calEvents)&&data.calEvents.length===0&&Array.isArray(data.bookings));
  requireThat(p.pageCount===Math.ceil(p.rowCount/p.pageSize));
  requireThat(data.bookings.length===(p.page<p.pageCount?p.pageSize:p.rowCount-p.pageSize*(p.pageCount-1)),'incomplete');
  const window=[instant(u.searchParams.get('startDT')),new Date(Date.parse(instant(u.searchParams.get('endDT')))+1).toISOString()];
  const totals=[p.rowCount,p.pageCount];
  if(this.window)requireThat(JSON.stringify(this.window)===JSON.stringify(window)&&JSON.stringify(this.totals)===JSON.stringify(totals),'incomplete');
  this.window=window;this.totals=totals;
  const rows=data.bookings.map(normalize);
  if(this.pages.has(p.page))requireThat(JSON.stringify(this.pages.get(p.page))===JSON.stringify(rows),'incomplete');
  this.pages.set(p.page,rows);
 }
 complete(){return this.totals&&this.pages.size===this.totals[1]&&Array.from({length:this.totals[1]},(_,i)=>i+1).every(p=>this.pages.has(p));}
 snapshot(){
  requireThat(this.complete(),'incomplete');
  const pages=[...this.pages.keys()].sort((a,b)=>a-b),rows=pages.flatMap(p=>this.pages.get(p));
  requireThat(rows.length===this.totals[0]&&new Set(rows.map(r=>r.id)).size===rows.length,'incomplete');
  return {schemaVersion:1,collectedAt:new Date().toISOString(),scope:SCOPE,windowStart:this.window[0],windowEnd:this.window[1],pagination:{rowCount:rows.length,pageCount:pages.length,pages},occurrences:rows};
 }
}
async function collect(){
 const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
 requireThat(process.env.DISPLAY,'browser_error');
 phase='launch';
 const browser=await chromium.launch({headless:false,executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',chromiumSandbox:true});
 const context=await browser.newContext({timezoneId:'America/Chicago'});
 const page=await context.newPage();page.setDefaultTimeout(30000);
 const pages=new Pages(),pending=new Set();let error=null,locationVerified=false,categoriesVerified=false;
 let rejectSource;const sourceFailed=new Promise((_,reject)=>{rejectSource=reject;});sourceFailed.catch(()=>{});
 function fail(code){if(!error){error=new SourceError(code);rejectSource(error);}}
 page.on('response',response=>{
  const u=new global.URL(response.url());
  if(u.hostname==='crux.portal.approach.app'){
   const action=response.headers()['x-amzn-waf-action'];
   if(action==='captcha'||action==='challenge'){fail('captcha');return;}
   if(response.request().resourceType()==='script'&&response.status()>=400){fail('source_http');return;}
  }
  if(u.hostname!=='widgets.api.prod.tilefive.com'||!['/cal','/categories','/locations','/locations/2'].includes(u.pathname))return;
  const task=(async()=>{
   try{
    if(response.status()!==200||!response.headers()['content-type']?.includes('json')){fail('source_http');return;}
    const data=await response.json();
    if(u.pathname==='/cal')pages.add(u,data);
    else if(u.pathname==='/categories'){
     requireThat(Array.isArray(data.data));
     requireThat(IDS.every(id=>data.data.some(c=>c.id===id&&c.name.trim()===CATEGORIES[id])));
     categoriesVerified=true;
    }else{
     const central=(Array.isArray(data)?data:[data]).find(l=>l.id===2);
     if(central){requireThat(central.timeZone===SCOPE.timeZone&&central.name==='Crux Climbing Center - Central');locationVerified=true;}
    }
   }catch(e){fail(e instanceof SourceError?e.code:'schema_error');}
  })();pending.add(task);task.finally(()=>pending.delete(task));
 });
 async function drain(){await page.waitForTimeout(1200);await Promise.all([...pending]);if(error)throw error;}
 try{
  const work=(async()=>{
   phase='navigate';await page.goto(URL,{waitUntil:'domcontentloaded',timeout:45000});
   const source=await page.locator('iframe[src*="crux.portal.approach.app"]').getAttribute('src');
   requireThat(source==='https://crux.portal.approach.app/schedule/embed?categoryIds=4&locationIds=2');
   if(error)throw error;
   await page.goto(source,{waitUntil:'domcontentloaded',timeout:45000});
   const iframe=page;
   const radio=iframe.locator('input[type="radio"][value="2"]');
   phase='location_radio';await radio.waitFor({timeout:45000});
   phase='location_select';await radio.check();
   requireThat(await radio.isChecked(),'browser_error');
   phase='location_save';await iframe.getByRole('button',{name:'Save',exact:true}).click();
   phase='schedule_load';await iframe.getByRole('button',{name:'Events',exact:true}).waitFor({timeout:60000});
   const frame=page.mainFrame();
   requireThat(frame,'browser_error');
   await drain();
   const text=await frame.locator('body').innerText();
   if(/confirm.*human|verify.*human|complete the security check|access denied/i.test(text))throw new SourceError('captcha');
   phase='category_select';await frame.getByRole('button',{name:'Events',exact:true}).click();
   await frame.getByRole('button',{name:'Clear',exact:true}).click();
   for(const name of Object.values(CATEGORIES))await frame.getByRole('menuitem',{name:new RegExp('^'+name+'\\s*$')}).click();
   await frame.getByRole('button',{name:'Save',exact:true}).click();
   await drain();
   phase='pagination';let unchanged=0,last=0;
   for(let attempt=0;attempt<100&&!pages.complete();attempt++){
    await frame.getByRole('row').last().scrollIntoViewIfNeeded();
    await frame.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
    await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
    await drain();
    unchanged=pages.pages.size===last?unchanged+1:0;last=pages.pages.size;
    if(unchanged>=5)throw new SourceError('incomplete');
   }
   await drain();requireThat(locationVerified&&categoriesVerified);
   return pages.snapshot();
  })();
  return await Promise.race([work,sourceFailed]);
 }finally{await browser.close();}
}
async function main(){
 const output=process.argv[2];requireThat(output,'schema_error');
 try{const snapshot=await collect();fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output+'.tmp',JSON.stringify(snapshot,null,2)+'\n');fs.renameSync(output+'.tmp',output);console.log(JSON.stringify({result:'ok',count:snapshot.occurrences.length,pages:snapshot.pagination.pageCount,windowStart:snapshot.windowStart,windowEnd:snapshot.windowEnd}));}
 catch(e){const code=e instanceof SourceError?e.code:(e.name==='TimeoutError'?'timeout':'browser_error');console.log(JSON.stringify({result:'failed',error:code,phase}));process.exitCode=2;}
}
module.exports={normalize,Pages,SCOPE,SourceError};
if(require.main===module)main();

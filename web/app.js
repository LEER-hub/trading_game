const state = { snapshot: null, symbol: "GOLD", side: "buy", range: 120, mode: "candles", hoverIndex: null };
const $ = id => document.getElementById(id);
const money = value => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(value);
const number = value => new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
const icons = { GOLD:"Au", SILVER:"Ag", WTI:"WT", BRENT:"Br", NATGAS:"NG", COPPER:"Cu" };

function currentAsset() { return state.snapshot?.assets[state.symbol]; }
function decimals(asset) { return asset?.decimals ?? 2; }
function priceText(value, asset = currentAsset()) { return Number(value).toLocaleString("en-US", { minimumFractionDigits: decimals(asset), maximumFractionDigits: decimals(asset) }); }
function signClass(value) { return value >= 0 ? "positive" : "negative"; }

function render(snapshot) {
  state.snapshot = snapshot;
  if (!snapshot.assets[state.symbol]) state.symbol = Object.keys(snapshot.assets)[0];
  const asset = currentAsset();
  $("sourceLabel").textContent = snapshot.source === "connected" ? "EXTERNAL DATA ANCHORED" : snapshot.source === "provider-error" ? "PROVIDER FALLBACK" : "SIMULATED MARKET";
  $("populationCount").textContent = number(snapshot.population);
  $("topEquity").textContent = money(snapshot.equity);
  $("topPnl").textContent = `${snapshot.pnl >= 0 ? "+" : ""}${money(snapshot.pnl)}`;
  $("topPnl").className = signClass(snapshot.pnl);
  renderAssetList();
  $("assetName").textContent = asset.name;
  $("assetSymbol").textContent = asset.symbol;
  $("assetUnit").textContent = asset.unit;
  $("assetIcon").textContent = icons[asset.symbol] || asset.symbol.slice(0,2);
  $("mainPrice").textContent = priceText(asset.price);
  $("mainChange").textContent = `${asset.change >= 0 ? "+" : ""}${asset.change.toFixed(2)}%`;
  $("mainChange").className = signClass(asset.change);
  $("ticketPrice").textContent = money(asset.price);
  $("cash").textContent = money(snapshot.cash);
  $("equity").textContent = money(snapshot.equity);
  $("portfolioPnl").textContent = `${snapshot.pnl >= 0 ? "+" : ""}${money(snapshot.pnl)}`;
  $("portfolioPnl").className = signClass(snapshot.pnl);
  $("positionLabel").textContent = `${asset.name} position`;
  $("position").textContent = Number(asset.position).toLocaleString(undefined,{maximumFractionDigits:4});
  $("activeAgents").textContent = number(asset.activeAgents);
  $("aiBuys").textContent = number(asset.aiBuys);
  $("aiSells").textContent = number(asset.aiSells);
  const sentimentWord = asset.sentiment > .15 ? "BULLISH" : asset.sentiment < -.15 ? "BEARISH" : "NEUTRAL";
  $("sentiment").textContent = sentimentWord;
  $("sentiment").className = signClass(asset.sentiment);
  $("sentimentScore").textContent = `${asset.sentiment >= 0 ? "+" : ""}${asset.sentiment.toFixed(2)} signal`;
  $("headline").textContent = asset.headline;
  const total = Math.max(1, asset.aiBuys + asset.aiSells), buyPct = asset.aiBuys / total * 100;
  $("buyFlow").style.width = `${buyPct}%`;
  $("flowLabel").textContent = `${buyPct.toFixed(0)}% BUY`;
  $("latestPriceTag").textContent = priceText(asset.price);
  updateEstimate();
  drawChart();
}

function renderAssetList() {
  const query = $("assetSearch").value.trim().toLowerCase();
  $("assetList").innerHTML = Object.values(state.snapshot.assets).filter(a => !query || `${a.name} ${a.symbol}`.toLowerCase().includes(query)).map(asset => `
    <button class="asset-row ${asset.symbol === state.symbol ? "active" : ""}" data-symbol="${asset.symbol}">
      <span class="asset-icon">${icons[asset.symbol] || asset.symbol.slice(0,2)}</span>
      <span class="asset-copy"><strong>${asset.name}</strong><span>${asset.symbol}</span></span>
      <span class="asset-quote"><strong>${priceText(asset.price, asset)}</strong><span class="${signClass(asset.change)}">${asset.change >= 0 ? "+" : ""}${asset.change.toFixed(2)}%</span></span>
    </button>`).join("");
  document.querySelectorAll(".asset-row").forEach(row => row.onclick = () => { state.symbol = row.dataset.symbol; state.hoverIndex = null; render(state.snapshot); });
}

function drawChart() {
  const canvas = $("priceChart"), box = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  if (!box.width || !box.height) return;
  canvas.width = Math.round(box.width * dpr); canvas.height = Math.round(box.height * dpr);
  const ctx = canvas.getContext("2d"); ctx.scale(dpr,dpr);
  const width = box.width, height = box.height, pad = {l:12,r:58,t:17,b:24};
  const candles = currentAsset().candles.slice(-state.range); if (!candles.length) return;
  const lows = candles.map(c=>c.low), highs = candles.map(c=>c.high), rawMin=Math.min(...lows), rawMax=Math.max(...highs), margin=(rawMax-rawMin || rawMax*.001)*.12;
  const min=rawMin-margin,max=rawMax+margin, plotW=width-pad.l-pad.r,plotH=height-pad.t-pad.b;
  const x=i=>pad.l+(i+.5)*plotW/candles.length, y=v=>pad.t+(max-v)/(max-min)*plotH;
  ctx.clearRect(0,0,width,height); ctx.lineWidth=1; ctx.font="9px Inter,system-ui";
  for(let i=0;i<=4;i++){ const yy=pad.t+i*plotH/4; ctx.strokeStyle="#19212d"; ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(width-pad.r,yy);ctx.stroke(); const val=max-i*(max-min)/4; ctx.fillStyle="#667286";ctx.fillText(priceText(val),width-pad.r+7,yy+3); }
  if(state.mode === "line"){
    const gradient=ctx.createLinearGradient(0,pad.t,0,height-pad.b); gradient.addColorStop(0,"rgba(32,212,155,.22)");gradient.addColorStop(1,"rgba(32,212,155,0)");
    ctx.beginPath(); candles.forEach((c,i)=>i?ctx.lineTo(x(i),y(c.close)):ctx.moveTo(x(i),y(c.close))); ctx.lineTo(x(candles.length-1),height-pad.b);ctx.lineTo(x(0),height-pad.b);ctx.closePath();ctx.fillStyle=gradient;ctx.fill();
    ctx.beginPath();candles.forEach((c,i)=>i?ctx.lineTo(x(i),y(c.close)):ctx.moveTo(x(i),y(c.close)));ctx.strokeStyle="#20d49b";ctx.lineWidth=1.6;ctx.stroke();
  } else {
    const slot=plotW/candles.length, body=Math.max(1,Math.min(7,slot*.62)); candles.forEach((c,i)=>{const up=c.close>=c.open,color=up?"#20d49b":"#ff5d70";ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x(i),y(c.high));ctx.lineTo(x(i),y(c.low));ctx.stroke();const top=y(Math.max(c.open,c.close)),bottom=y(Math.min(c.open,c.close));ctx.fillRect(x(i)-body/2,top,body,Math.max(1,bottom-top));});
  }
  const latestY=y(candles[candles.length-1].close); $("latestPriceTag").style.top=`${latestY}px`;
  ctx.setLineDash([3,4]);ctx.strokeStyle="rgba(32,212,155,.35)";ctx.beginPath();ctx.moveTo(pad.l,latestY);ctx.lineTo(width-pad.r,latestY);ctx.stroke();ctx.setLineDash([]);
  if(state.hoverIndex!==null){const i=Math.max(0,Math.min(candles.length-1,state.hoverIndex));ctx.strokeStyle="#536076";ctx.beginPath();ctx.moveTo(x(i),pad.t);ctx.lineTo(x(i),height-pad.b);ctx.stroke();}
  canvas._chartMeta={candles,x,y,pad,plotW};
}

function updateEstimate(){ const asset=currentAsset(); if(!asset)return; const qty=Math.max(0,Number($("quantity").value)||0); $("estimatedValue").textContent=money(qty*asset.price); $("placeOrder").textContent=`${state.side === "buy" ? "Buy" : "Sell"} ${asset.symbol}`; }
async function placeOrder(){ const quantity=Number($("quantity").value); $("placeOrder").disabled=true; try { const response=await fetch("/api/order",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({symbol:state.symbol,side:state.side,quantity})}); const payload=await response.json(); if(!payload.ok)throw new Error(payload.error); $("orderMessage").textContent=`${state.side.toUpperCase()} ${quantity} ${state.symbol} filled at ${priceText(payload.trade.price)}`; $("orderMessage").className="order-message positive"; render(payload.portfolio); } catch(error){ $("orderMessage").textContent=error.message;$("orderMessage").className="order-message negative"; } finally{$("placeOrder").disabled=false;} }

function setSide(side){state.side=side;$("buyTab").classList.toggle("active",side==="buy");$("sellTab").classList.toggle("active",side==="sell");$("placeOrder").className=`order-button ${side}`;updateEstimate();}
$("buyTab").onclick=()=>setSide("buy"); $("sellTab").onclick=()=>setSide("sell");
$("quantity").oninput=updateEstimate; $("increaseQty").onclick=()=>{$("quantity").value=(Number($("quantity").value)||0)+1;updateEstimate();}; $("decreaseQty").onclick=()=>{$("quantity").value=Math.max(.01,(Number($("quantity").value)||0)-1);updateEstimate();};
$("placeOrder").onclick=placeOrder; $("assetSearch").oninput=()=>state.snapshot&&renderAssetList();
document.querySelectorAll("[data-mode]").forEach(button=>button.onclick=()=>{document.querySelectorAll("[data-mode]").forEach(b=>b.classList.remove("active"));button.classList.add("active");state.mode=button.dataset.mode;drawChart();});
document.querySelectorAll("[data-range]").forEach(button=>button.onclick=()=>{document.querySelectorAll("[data-range]").forEach(b=>b.classList.remove("active"));button.classList.add("active");state.range=Number(button.dataset.range);drawChart();});
$("priceChart").addEventListener("mousemove",event=>{const meta=event.currentTarget._chartMeta;if(!meta)return;const rect=event.currentTarget.getBoundingClientRect(),px=event.clientX-rect.left;state.hoverIndex=Math.floor((px-meta.pad.l)/meta.plotW*meta.candles.length);state.hoverIndex=Math.max(0,Math.min(meta.candles.length-1,state.hoverIndex));const candle=meta.candles[state.hoverIndex],tip=$("chartTooltip");tip.classList.remove("hidden");tip.style.left=`${Math.min(rect.width-145,Math.max(8,px+12))}px`;tip.style.top="14px";tip.innerHTML=`<b>${new Date(candle.time).toLocaleTimeString()}</b><br>O ${priceText(candle.open)} &nbsp; H ${priceText(candle.high)}<br>L ${priceText(candle.low)} &nbsp; C ${priceText(candle.close)}<br>AI flow ${number(candle.volume)}`;drawChart();});
$("priceChart").addEventListener("mouseleave",()=>{state.hoverIndex=null;$("chartTooltip").classList.add("hidden");drawChart();});
new ResizeObserver(drawChart).observe($("priceChart")); setInterval(()=>$("clock").textContent=new Date().toLocaleTimeString("en-GB"),500);

fetch("/api/snapshot").then(r=>r.json()).then(render).catch(console.error);
const stream=new EventSource("/api/stream"); stream.onmessage=event=>render(JSON.parse(event.data)); stream.onerror=()=>{$("sourceLabel").textContent="RECONNECTING…";};

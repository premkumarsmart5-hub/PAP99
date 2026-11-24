const C="signals-v12", FILES=["./","./index.html","./manifest.webmanifest","./icon-192.png","./icon-512.png"];
self.addEventListener("install",e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(FILES)));self.skipWaiting();});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))));self.clients.claim();});
self.addEventListener("fetch",e=>{
  const u=new URL(e.request.url);
  if(e.request.method!=="GET"||u.origin!==location.origin) return;   // never touch API calls or other sites
  e.respondWith(fetch(e.request).then(r=>{
    if(r.ok&&r.type==="basic"){const cp=r.clone();caches.open(C).then(c=>c.put(e.request,cp));}  // cache only good same-site files
    return r;
  }).catch(()=>caches.match(e.request)));
});

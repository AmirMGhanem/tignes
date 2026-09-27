"""Builds _site/index.html: pulls Tignes–Val d'Isère runs & lifts (OpenStreetMap via OpenSkiData / SkiNavIndexes),
computes length, drop, steepness, facing and a snow-holding estimate, and injects them into template.html."""
import urllib.request, gzip, sqlite3, json, math, struct, os
TAG = "indexes-2026-09-17"
BASE = f"https://github.com/obewi/SkiNavIndexes/releases/download/{TAG}/"
NAME = "Tignes - Val d'Isère"

def get(url, path):
    with urllib.request.urlopen(url, timeout=300) as r, open(path, "wb") as f: f.write(r.read())
    return path

def gunzip(src, dst):
    with gzip.open(src) as i, open(dst, "wb") as o: o.write(i.read())
    return dst

def parse(b, o=0):
    e = '<' if b[o] == 1 else '>'; o += 1
    t = struct.unpack_from(e+'I', b, o)[0]; o += 4; dim = 2
    if t & 0x80000000: dim += 1
    if t & 0x40000000: dim += 1
    if t & 0x20000000: o += 4
    t &= 0x0FFFFFFF
    if t >= 1000:
        k = t // 1000; t %= 1000; dim = 2 + (k in (1, 3)) + (k in (2, 3))
    f = e + 'd'*dim; s = 8*dim
    def pts(o):
        n = struct.unpack_from(e+'I', b, o)[0]; o += 4; out = []
        for _ in range(n):
            v = struct.unpack_from(f, b, o); o += s; out.append((v[0], v[1], v[2] if dim > 2 else None))
        return out, o
    if t == 1:
        v = struct.unpack_from(f, b, o); o += s; return ('P', [[(v[0], v[1], None)]]), o
    if t == 2:
        p, o = pts(o); return ('L', [p]), o
    if t == 3:
        nr = struct.unpack_from(e+'I', b, o)[0]; o += 4; r = []
        for _ in range(nr):
            p, o = pts(o); r.append(p)
        return ('A', r), o
    if t in (4, 5, 6, 7):
        n = struct.unpack_from(e+'I', b, o)[0]; o += 4; kind = None; parts = []
        for _ in range(n):
            (k, pp), o = parse(b, o); kind = kind or k; parts += pp
        return (kind, parts), o
    raise ValueError(t)

def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    d = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*6371000*math.asin(math.sqrt(d))

def bearing(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    y = math.sin(lo2-lo1)*math.cos(la2); x = math.cos(la1)*math.sin(la2)-math.sin(la1)*math.cos(la2)*math.cos(lo2-lo1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def steep_score(pct):
    d = math.degrees(math.atan(pct/100))
    return 1 if d < 11 else 2 if d < 17 else 3 if d < 22 else 4 if d < 27 else 5

def snow_score(alt, asp):
    a = 3 if alt >= 2700 else 2 if alt >= 2400 else 1 if alt >= 2100 else 0
    s = 1 if asp is None else 2 if (asp >= 315 or asp < 45) else 0 if 135 <= asp < 225 else 1
    return max(1, min(5, a + s))

os.makedirs("_work", exist_ok=True); os.makedirs("_site", exist_ok=True)
cat = sqlite3.connect(gunzip(get(BASE+"catalog.sqlite.gz", "_work/c.gz"), "_work/catalog.sqlite"))
rid, pack = cat.execute("select r.id, rp.pack_id from resorts r join resort_packs rp on rp.resort_id=r.id where r.name=?", (NAME,)).fetchone()
db = sqlite3.connect(gunzip(get(BASE+pack+".sqlite.gz", "_work/p.gz"), "_work/pack.sqlite"))

runs = []
for name, diff, g, pj in db.execute("select r.name,r.difficulty,r.geometry_wkb,r.properties_json from runs r join run_resorts x on x.run_id=r.id where x.resort_id=?", (rid,)):
    (k, parts), _ = parse(g); P = json.loads(pj); uses = P.get('uses') or []
    prof = P.get('elevationProfile') or {}; H = prof.get('heights') or []; res = prof.get('resolution') or 25
    for p in parts:
        if len(p) < 2: continue
        o = {'n': name or '', 'd': diff or '', 'k': k, 'p': 1 if 'snow_park' in uses else 0,
             'c': [[round(q[1], 5), round(q[0], 5)] for q in p]}
        if k == 'L':
            ln = sum(hav(p[i], p[i+1]) for i in range(len(p)-1)); zs = [q[2] for q in p if q[2] is not None]
            if len(H) >= 3 and len(parts) == 1:
                top, bot = max(H), min(H); w = 4 if len(H) > 5 else 1
                mx = max(max(((H[i]-H[i+w])/(w*res)*100 for i in range(len(H)-w)), default=0), 0)
                alt = sum(H)/len(H); start, end = (p[0], p[-1]) if H[0] >= H[-1] else (p[-1], p[0])
            elif zs:
                top, bot = max(zs), min(zs); mx = None; alt = sum(zs)/len(zs)
                start, end = (p[0], p[-1]) if zs[0] >= zs[-1] else (p[-1], p[0])
            else:
                top = bot = mx = alt = None; start, end = p[0], p[-1]
            drop = (top - bot) if top is not None else None
            avg = drop/ln*100 if (drop is not None and ln > 0) else None
            asp = bearing(start, end) if ln > 30 else None
            if mx is None and avg is not None: mx = avg
            o['s'] = {'len': round(ln), 'drop': round(drop) if drop is not None else None,
                      'top': round(top) if top else None, 'bot': round(bot) if bot else None,
                      'avg': round(avg) if avg is not None else None, 'max': round(mx) if mx is not None else None,
                      'ss': steep_score(mx) if mx is not None else None, 'asp': round(asp) if asp is not None else None,
                      'alt': round(alt) if alt else None, 'sn': snow_score(alt, asp) if alt else None}
        runs.append(o)

lifts = []
for name, lt, g in db.execute("select l.name,l.lift_type,l.geometry_wkb from lifts l join lift_resorts x on x.lift_id=l.id where x.resort_id=?", (rid,)):
    (k, parts), _ = parse(g)
    for p in parts:
        zs = [q[2] for q in p if q[2] is not None]
        lifts.append({'n': name or '', 't': lt or '', 'c': [[round(q[1], 5), round(q[0], 5)] for q in p],
                      's': [round(sum(hav(p[i], p[i+1]) for i in range(len(p)-1))), round(min(zs)) if zs else None, round(max(zs)) if zs else None]})

data = json.dumps({'runs': runs, 'lifts': lifts}, separators=(',', ':'), ensure_ascii=False)
html = open("template.html", encoding="utf-8").read().replace("/*SKIDATA*/", data)
open("_site/index.html", "w", encoding="utf-8").write(html)
open("_site/.nojekyll", "w").close()
print(f"runs={len(runs)} lifts={len(lifts)} bytes={len(html)}")

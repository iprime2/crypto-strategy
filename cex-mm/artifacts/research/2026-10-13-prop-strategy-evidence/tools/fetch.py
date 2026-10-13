import sys, re, html, subprocess, os, json
urls = [l.strip() for l in open(sys.argv[1]) if l.strip()]
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
def strip(h):
    h = re.sub(r'(?is)<(script|style|noscript|svg|header|footer|nav)[^>]*>.*?</\1>', ' ', h)
    h = re.sub(r'(?s)<[^>]+>', ' ', h)
    h = html.unescape(h)
    h = re.sub(r'[ \t\r\f\v]+', ' ', h)
    h = re.sub(r'\n\s*\n+', '\n', h)
    return h.strip()
for i,u in enumerate(urls):
    fn = os.path.join(out, f"p{i:02d}.txt")
    try:
        r = subprocess.run(["curl","-sSL","--max-time","40","-A","Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36","-H","Accept-Language: en","-w","\n@@HTTP:%{http_code}@@",u],capture_output=True,text=True,errors="replace")
        body = r.stdout
        m = re.search(r'@@HTTP:(\d+)@@\s*$', body)
        code = m.group(1) if m else "?"
        body = body[:m.start()] if m else body
        t = strip(body)
        open(fn,"w").write(t)
        print(f"[{i:02d}] {code} {len(t):7d} chars  {u}")
        if r.stderr.strip(): print("     err:", r.stderr.strip()[:200])
    except Exception as e:
        print(f"[{i:02d}] EXC {u} {e}")

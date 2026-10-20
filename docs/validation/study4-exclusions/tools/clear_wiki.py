import zipfile,re,json,sys,html,collections
z=zipfile.ZipFile(sys.argv[1])
ss=[]
for si in re.findall(rb"<si>(.*?)</si>", z.read("xl/sharedStrings.xml"), flags=re.S):
    ss.append(html.unescape("".join(t.decode() for t in re.findall(rb"<t[^>]*>(.*?)</t>", si, flags=re.S))))
sheet=z.read("xl/worksheets/sheet1.xml")
rows=[]
for r in re.findall(rb"<row [^>]*>(.*?)</row>", sheet, flags=re.S):
    cells={}
    for m in re.finditer(rb'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', r, flags=re.S):
        col,attrs,body=m.group(1).decode(),m.group(2),m.group(3) or b""
        v=re.search(rb"<v>(.*?)</v>",body,flags=re.S)
        if v is None:
            t=re.search(rb"<t[^>]*>(.*?)</t>",body,flags=re.S); val=html.unescape(t.group(1).decode()) if t else None
        else:
            val=v.group(1).decode()
            if b't="s"' in attrs: val=ss[int(val)]
        cells[col]=val
    rows.append(cells)
hdr=rows[0]; name={c:(hdr[c] or "").strip() for c in hdr}
out=[]
for r in rows[1:]:
    d={name.get(c,c):v for c,v in r.items()}
    out.append(d)
print(json.dumps({"header":list(name.values()),"n":len(out)}),file=sys.stderr)
urlcol=[n for n in name.values() if n.lower()=="url"]
print(urlcol,file=sys.stderr)
res=[]
for d in out:
    u=(d.get(urlcol[0]) or "").strip()
    if "wikipedia.org" in u:
        res.append({"clear_id":d.get("ID"),"url":u,"title":d.get("Title"),"author":d.get("Author"),"pub_year":d.get("Pub Year")})
json.dump(res,open(sys.argv[2],"w"),ensure_ascii=False,indent=0)
print(len(res), collections.Counter(re.sub(r"(https?://[^/]+).*",r"\1",x["url"]) for x in res),file=sys.stderr)

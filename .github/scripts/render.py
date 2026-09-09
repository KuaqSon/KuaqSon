"""Render Teenage Engineering styled SVG cards from GitHub GraphQL data. Stdlib only."""
import json, os, re, sys, urllib.request
from xml.sax.saxutils import escape as esc

USER = os.environ.get("GH_USER", "KuaqSon")
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist"
PINS = ["yt-music", "mokuton", "flash-commit", "nestjs-starter"]

BG, INK, MUTE, LINE, ORANGE = "#e6e6e4", "#1a1a1a", "#6b6b69", "#c9c9c7", "#ff5f1f"
FONT = "font-family=\"'SF Mono','Menlo','Consolas','Liberation Mono',monospace\""

QUERY = """
query($login:String!, $pins:String!) {
  user(login:$login) {
    followers { totalCount }
    repositories(first:100, ownerAffiliations:OWNER, isFork:false, orderBy:{field:STARGAZERS, direction:DESC}) {
      totalCount
      nodes { name stargazerCount languages(first:10, orderBy:{field:SIZE, direction:DESC}) { edges { size node { name color } } } }
    }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection {
      totalCommitContributions restrictedContributionsCount
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
  }
  search(query:$pins, type:REPOSITORY, first:10) { nodes { ... on Repository {
    name description stargazerCount forkCount primaryLanguage { name color } } } }
}"""


def gql():
    pins = " ".join(f"repo:{USER}/{r}" for r in PINS)
    body = json.dumps({"query": QUERY, "variables": {"login": USER, "pins": pins}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", body,
        {"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "Content-Type": "application/json", "User-Agent": USER})
    data = json.load(urllib.request.urlopen(req))
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]


# ---------- svg primitives ----------
def panel(w, h, title, idx):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" {FONT}>',
        f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="12" fill="{BG}" stroke="{LINE}"/>',
        f'<g fill="#cfcfcd" stroke="#b5b5b3" stroke-width=".8"><circle cx="14" cy="14" r="3"/><circle cx="{w-14}" cy="14" r="3"/>'
        f'<circle cx="14" cy="{h-14}" r="3"/><circle cx="{w-14}" cy="{h-14}" r="3"/></g>',
        f'<text x="30" y="30" font-size="9" fill="{MUTE}" letter-spacing="1.5">{esc(title.upper())}</text>',
        f'<text x="{w-30}" y="30" font-size="9" fill="{MUTE}" letter-spacing="1.5" text-anchor="end">NQSON–01 · {idx}</text>',
        f'<line x1="30" y1="38" x2="{w-30}" y2="38" stroke="{LINE}" stroke-width=".8"/>']


def txt(x, y, s, size=11, fill=INK, anchor="start", weight=400, ls=0):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}" letter-spacing="{ls}">{esc(str(s))}</text>')


def meter(x, y, w, frac, delay=0):
    fill_w = max(2, round(w * min(1, frac)))
    return (f'<rect x="{x}" y="{y}" width="{w}" height="6" rx="1" fill="{INK}" opacity=".12"/>'
            f'<rect x="{x}" y="{y}" width="{fill_w}" height="6" rx="1" fill="{ORANGE}">'
            f'<animate attributeName="width" from="0" to="{fill_w}" dur="1.2s" begin="{delay}s" fill="freeze" '
            f'calcMode="spline" keySplines=".2 .8 .2 1"/></rect>')


def wrap(s, n):
    words, lines, cur = (s or "").split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines[:2]


def fmt(n):
    return f"{n/1000:.1f}k" if n >= 1000 else str(n)


# ---------- cards ----------
def stats_card(u):
    c = u["contributionsCollection"]
    stars = sum(r["stargazerCount"] for r in u["repositories"]["nodes"])
    commits = c["totalCommitContributions"] + c["restrictedContributionsCount"]
    # ponytail: fixed caps for the meters; bump when a number outgrows its bar
    rows = [("STARS", stars, 100), ("COMMITS · 1Y", commits, 2000),
            ("PULL REQUESTS", u["pullRequests"]["totalCount"], 300), ("ISSUES", u["issues"]["totalCount"], 100),
            ("FOLLOWERS", u["followers"]["totalCount"], 100), ("REPOSITORIES", u["repositories"]["totalCount"], 100)]
    s = panel(400, 200, "telemetry · stats", "05A")
    for i, (label, val, cap) in enumerate(rows):
        y = 62 + i * 23
        s += [txt(30, y, label, 9, MUTE, ls=1.2), txt(190, y, fmt(val), 12, INK, "end", 700),
              meter(210, y - 6, 160, val / cap, i * .1)]
    s.append('</svg>')
    return "\n".join(s)


def langs_card(u):
    tot = {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            tot[e["node"]["name"]] = tot.get(e["node"]["name"], 0) + e["size"]
    top = sorted(tot.items(), key=lambda kv: -kv[1])[:6]
    total = sum(tot.values()) or 1
    s = panel(400, 200, "telemetry · languages", "05B")
    for i, (name, size) in enumerate(top):
        y = 62 + i * 23
        pct = size / total
        s += [txt(30, y, name.upper(), 9, MUTE, ls=1.2), txt(190, y, f"{pct*100:.1f}%", 12, INK, "end", 700),
              meter(210, y - 6, 160, size / top[0][1], i * .1)]
    s.append('</svg>')
    return "\n".join(s)


def streak_card(u):
    cal = u["contributionsCollection"]["contributionCalendar"]
    counts = [d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]]
    cur = 0
    for c in reversed(counts[:-1] if counts and counts[-1] == 0 else counts):  # today may still be empty
        if c == 0:
            break
        cur += 1
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    s = panel(820, 150, "telemetry · contributions", "05C")
    for i, (label, val, unit) in enumerate([("TOTAL · 1Y", cal["totalContributions"], "contributions"),
                                            ("CURRENT STREAK", cur, "days"), ("LONGEST STREAK", longest, "days")]):
        x = 30 + i * 150
        s += [txt(x, 58, label, 9, MUTE, ls=1.2), txt(x, 92, val, 30, ORANGE if i == 1 else INK, weight=700, ls=-1),
              txt(x, 108, unit, 9, MUTE, ls=1)]
    mx = max(counts) or 1
    s.append(f'<rect x="478" y="48" width="312" height="72" rx="4" fill="{INK}"/>')
    for wi, w in enumerate(cal["weeks"][-40:]):
        for di, d in enumerate(w["contributionDays"]):
            c = d["contributionCount"]
            op = .12 if c == 0 else .35 + .65 * (c / mx)
            s.append(f'<rect x="{486 + wi*7.6:.1f}" y="{54 + di*8.6:.1f}" width="5.6" height="6.6" rx="1" '
                     f'fill="{ORANGE}" opacity="{op:.2f}"><animate attributeName="opacity" values="0;{op:.2f}" '
                     f'dur=".4s" begin="{wi*.03:.2f}s" fill="freeze"/></rect>')
    s.append(txt(790, 134, "LAST 40 WEEKS", 8, MUTE, "end", ls=1.2))
    s.append('</svg>')
    return "\n".join(s)


def pin_card(r, idx):
    s = panel(400, 130, f"featured · {idx:02d}", f"04{chr(64+idx)}")
    s.append(txt(30, 62, r["name"], 16, INK, weight=700, ls=-.5))
    for i, line in enumerate(wrap(re.sub(r":\w+:", "", r.get("description") or "—"), 52)):
        s.append(txt(30, 82 + i * 14, line, 10, "#3a3a3a"))
    lang = r.get("primaryLanguage") or {}
    x = 30
    if lang:
        s += [f'<circle cx="{x+4}" cy="113" r="4" fill="{lang.get("color") or ORANGE}"/>',
              txt(x + 14, 116, lang["name"].upper(), 9, MUTE, ls=1.2)]
        x += 14 + len(lang["name"]) * 7.5 + 20
    s += [txt(x, 116, f"★ {r['stargazerCount']}", 9, MUTE, ls=1), txt(x + 50, 116, f"⑂ {r['forkCount']}", 9, MUTE, ls=1)]
    s.append(f'<circle cx="364" cy="112" r="4" fill="{ORANGE}">'
             f'<animate attributeName="opacity" values="1;.3;1" dur="2s" repeatCount="indefinite"/></circle>')
    s.append('</svg>')
    return "\n".join(s)


def render(d):
    u = d["user"]
    out = {"stats.svg": stats_card(u), "langs.svg": langs_card(u), "streak.svg": streak_card(u)}
    by_name = {r["name"]: r for r in d["search"]["nodes"]}
    for i, name in enumerate(PINS, 1):
        if name in by_name:
            out[f"pin-{name}.svg"] = pin_card(by_name[name], i)
    return out


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    out = render(gql())
    for f, svg in out.items():
        open(os.path.join(OUT, f), "w").write(svg)
    print("wrote", ", ".join(out))

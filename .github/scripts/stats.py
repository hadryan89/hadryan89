"""Render the profile stats card (assets/stats-dark.svg and assets/stats-light.svg).

Runs daily from .github/workflows/stats.yml. Uses GITHUB_TOKEN, so languages
and stars come from public repositories; contribution counts include private
contributions because the profile has them enabled.
"""
import datetime as dt
import json
import os
import pathlib
import urllib.request

USER = os.environ.get("STATS_USER", "hadryan89")
# STATS_TOKEN (optional PAT) also counts private repositories in languages and PRs
TOKEN = os.environ.get("STATS_TOKEN") or os.environ["GITHUB_TOKEN"]
ASSETS = pathlib.Path(__file__).resolve().parents[2] / "assets"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    pullRequests(states: MERGED) { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

THEMES = {
    "dark": {"text": "#e6edf3", "muted": "#8b949e", "line": "#30363d", "track": "#161b22"},
    "light": {"text": "#1f2328", "muted": "#59636e", "line": "#d0d7de", "track": "#eff2f5"},
}


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": USER},
    )
    body = json.load(urllib.request.urlopen(req))
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]["user"]


def streaks(days):
    counts = [d["contributionCount"] for d in sorted(days, key=lambda d: d["date"])]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    # Today may still be empty; the streak is only broken once yesterday is.
    if counts and counts[-1] == 0:
        counts = counts[:-1]
    current = 0
    for c in reversed(counts):
        if not c:
            break
        current += 1
    return current, longest


def languages(repos, top=5):
    sizes, colors = {}, {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    total = sum(sizes.values()) or 1
    ranked = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:top]
    return [(name, size / total * 100, colors[name]) for name, size in ranked]


def fmt(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def render(stats, langs, t):
    font = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="840" height="190" viewBox="0 0 840 190" '
        f'role="img" aria-label="GitHub stats for {USER}">',
        f"<title>GitHub stats for {USER}</title>",
        f'<style>text{{font-family:{font};font-variant-numeric:tabular-nums}}'
        f".v{{font-size:26px;font-weight:600;fill:{t['text']}}}"
        f".l{{font-size:11px;letter-spacing:.08em;fill:{t['muted']}}}"
        f".n{{font-size:13px;fill:{t['text']}}}.p{{font-size:13px;fill:{t['muted']}}}</style>",
        f'<rect x="0.5" y="0.5" width="839" height="189" rx="8" fill="none" stroke="{t["line"]}"/>',
    ]

    for i, (label, value) in enumerate(stats):
        x, y = 32 + (i % 3) * 150, 62 + (i // 3) * 78
        out.append(f'<text class="v" x="{x}" y="{y}">{value}</text>')
        out.append(f'<text class="l" x="{x}" y="{y + 22}">{label.upper()}</text>')

    out.append(f'<line x1="496" y1="28" x2="496" y2="162" stroke="{t["line"]}"/>')

    bx, bw = 528, 280
    out.append(f'<text class="l" x="{bx}" y="40">TOP LANGUAGES</text>')
    out.append(f'<clipPath id="bar"><rect x="{bx}" y="54" width="{bw}" height="8" rx="4"/></clipPath>')
    out.append(f'<rect x="{bx}" y="54" width="{bw}" height="8" rx="4" fill="{t["track"]}"/>')
    offset = bx
    for _, pct, color in langs:
        w = bw * pct / 100
        out.append(f'<rect clip-path="url(#bar)" x="{offset:.2f}" y="54" width="{w:.2f}" height="8" fill="{color}"/>')
        offset += w
    for i, (name, pct, color) in enumerate(langs):
        y = 88 + i * 19
        out.append(f'<rect x="{bx}" y="{y - 9}" width="10" height="10" rx="2" fill="{color}"/>')
        out.append(f'<text class="n" x="{bx + 18}" y="{y}">{name}</text>')
        out.append(f'<text class="p" x="{bx + bw}" y="{y}" text-anchor="end">{pct:.1f}%</text>')

    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    user = fetch()
    cc = user["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    current, longest = streaks(days)
    repos = user["repositories"]["nodes"]
    stats = [
        ("Contributions", fmt(cc["contributionCalendar"]["totalContributions"])),
        ("Active days", fmt(sum(1 for d in days if d["contributionCount"]))),
        ("Merged PRs", fmt(user["pullRequests"]["totalCount"])),
        ("Current streak", f"{current} {'day' if current == 1 else 'days'}"),
        ("Longest streak", f"{longest} {'day' if longest == 1 else 'days'}"),
        ("Stars", fmt(sum(r["stargazerCount"] for r in repos))),
    ]
    langs = languages(repos)
    for name, theme in THEMES.items():
        (ASSETS / f"stats-{name}.svg").write_text(render(stats, langs, theme), encoding="utf-8", newline="\n")
    print(f"updated {dt.date.today()}: {stats}")


if __name__ == "__main__":
    main()

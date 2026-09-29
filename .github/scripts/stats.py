"""Render the profile stats card (assets/stats-dark.svg and assets/stats-light.svg).

Runs daily from .github/workflows/stats.yml. Uses GITHUB_TOKEN, so languages
and merged PRs come from public repositories; contribution counts include
private contributions because the profile has them enabled.
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
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

# Same palette as GitHub's contribution graph (and assets/contrib-grid-*.svg)
THEMES = {
    "dark": {
        "text": "#e6edf3", "muted": "#8b949e", "line": "#30363d", "empty": "#161b22",
        "levels": ["#0e4429", "#006d32", "#26a641", "#39d353"],
    },
    "light": {
        "text": "#1f2328", "muted": "#59636e", "line": "#d0d7de", "empty": "#ebedf0",
        "levels": ["#9be9a8", "#40c463", "#30a14e", "#216e39"],
    },
}

W, H, PAD = 840, 272, 28
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"


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


def streaks(counts):
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


def languages(repos, top=6):
    sizes, colors = {}, {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    total = sum(sizes.values()) or 1
    ranked = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:top]
    return [(name, size / total * 100, colors[name]) for name, size in ranked]


def render(metrics, weeks, langs, t):
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="GitHub stats for {USER}">',
        f"<title>GitHub stats for {USER}</title>",
        f"<style>text{{font-family:{FONT};font-variant-numeric:tabular-nums}}"
        f".h{{font-size:14px;font-weight:600;fill:{t['text']}}}"
        f".s{{font-size:12px;fill:{t['muted']}}}"
        f".v{{font-size:28px;font-weight:600;fill:{t['text']};letter-spacing:-.02em}}"
        f".u{{font-size:13px;font-weight:400;fill:{t['muted']};letter-spacing:0}}"
        f".n{{font-size:12px;fill:{t['text']}}}</style>",
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="none" stroke="{t["line"]}"/>',
        f'<text class="h" x="{PAD}" y="40">{USER}</text>',
        f'<text class="s" x="{W - PAD}" y="40" text-anchor="end">Last 12 months</text>',
    ]

    # Headline numbers
    col = (W - 2 * PAD) / len(metrics)
    for i, (label, value, unit) in enumerate(metrics):
        x = PAD + i * col
        suffix = f'<tspan class="u" dx="5">{unit}</tspan>' if unit else ""
        out.append(f'<text class="v" x="{x:.1f}" y="92">{value}{suffix}</text>')
        out.append(f'<text class="s" x="{x:.1f}" y="114">{label}</text>')

    out.append(f'<line x1="{PAD}" y1="140" x2="{W - PAD}" y2="140" stroke="{t["line"]}"/>')

    # Weekly contributions, one column per week
    cx, cw, top, ch = PAD, 470, 190, 52
    out.append(f'<text class="s" x="{cx}" y="170">Contributions per week</text>')
    step = cw / len(weeks)
    peak = max(weeks) or 1
    for i, total in enumerate(weeks):
        x = cx + i * step
        if total:
            h = max(4, ch * total / peak)
            color = t["levels"][min(3, int(4 * total / (peak + 1)))]
        else:
            h, color = 4, t["empty"]
        out.append(f'<rect x="{x:.1f}" y="{top + ch - h:.1f}" width="{step - 3:.1f}" height="{h:.1f}" rx="1.5" fill="{color}"/>')

    # Languages
    lx, lw = 548, W - PAD - 548
    out.append(f'<text class="s" x="{lx}" y="170">Top languages</text>')
    out.append(f'<clipPath id="bar"><rect x="{lx}" y="186" width="{lw}" height="8" rx="4"/></clipPath>')
    offset = lx
    for _, pct, color in langs:
        w = lw * pct / 100
        out.append(f'<rect clip-path="url(#bar)" x="{offset:.2f}" y="186" width="{w + .5:.2f}" height="8" fill="{color}"/>')
        offset += w
    for i, (name, pct, color) in enumerate(langs):
        x, y = lx + (i % 2) * (lw / 2), 220 + (i // 2) * 20
        out.append(f'<circle cx="{x + 4}" cy="{y - 4}" r="4" fill="{color}"/>')
        out.append(f'<text class="n" x="{x + 14}" y="{y}">{name} <tspan class="s">{pct:.1f}%</tspan></text>')

    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    user = fetch()
    cal = user["contributionsCollection"]["contributionCalendar"]
    week_days = [w["contributionDays"] for w in cal["weeks"]]
    counts = [d["contributionCount"] for days in week_days for d in sorted(days, key=lambda d: d["date"])]
    current, longest = streaks(counts)
    metrics = [
        ("Contributions", f"{cal['totalContributions']:,}", ""),
        ("Active days", str(sum(1 for c in counts if c)), ""),
        ("Merged pull requests", str(user["pullRequests"]["totalCount"]), ""),
        ("Current streak", str(current), "day" if current == 1 else "days"),
        ("Longest streak", str(longest), "day" if longest == 1 else "days"),
    ]
    weeks = [sum(d["contributionCount"] for d in days) for days in week_days]
    langs = languages(user["repositories"]["nodes"])
    for name, theme in THEMES.items():
        (ASSETS / f"stats-{name}.svg").write_text(render(metrics, weeks, langs, theme), encoding="utf-8", newline="\n")
    print(f"updated {dt.date.today()}: {metrics}")


if __name__ == "__main__":
    main()

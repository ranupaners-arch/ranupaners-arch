#!/usr/bin/env python3
"""Perbarui kartu neofetch (dark_mode.svg & light_mode.svg) milik ranupaners-arch.

Meniru alur today.py Andrew6rant:
  1. Hitung uptime sejak 25 Juni 2004.
  2. Ambil statistik lewat GitHub GraphQL API: repo, repo kontribusi, star,
     commit, follower, dan baris kode (+/-) dengan cache per repo.
  3. Tulis nilai ke elemen SVG berdasarkan id dan sesuaikan titik-titik
     penyambung supaya kolom tetap rata kanan.

Token dibaca dari env ACCESS_TOKEN (PAT) atau GITHUB_TOKEN. Token tidak
pernah ditulis ke berkas mana pun.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

import requests
from dateutil import relativedelta
from lxml import etree

ROOT = Path(__file__).resolve().parent
USER_NAME = os.environ.get("USER_NAME") or "ranupaners-arch"
BIRTHDAY = datetime.datetime(2004, 6, 25)
CACHE_DIR = ROOT / "cache"
API = "https://api.github.com/graphql"

# --------------------------------------------------------------------------- #
# Tata letak: lebar baris info (karakter) dan posisi kolom " | ".
# Dipakai bersama tools/build_cards.py.
# --------------------------------------------------------------------------- #
LINE_W = 72
COL = 44


def dots(width: int) -> str:
    """Isi penyambung selebar `width` karakter: ' ..... '."""
    if width <= 0:
        return ""
    if width == 1:
        return " "
    if width == 2:
        return ". "
    return " " + "." * (width - 2) + " "


def fmt(n) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


def layout(v: dict) -> dict:
    """Kembalikan {id: teks} untuk semua nilai dinamis + titik penyambungnya."""
    out = {k: fmt(x) for k, x in v.items()}
    # . Uptime: ...... 22 years, 4 months, 16 days
    out["age_data_dots"] = dots(LINE_W - len(". Uptime:") - len(out["age_data"]))
    # . Repos: .. 12 {Contributed: 15} | Stars: ...... 3
    left = len(". Repos:") + len(out["repo_data"]) + len(" {Contributed: ") + len(out["contrib_data"]) + 1
    out["repo_data_dots"] = dots(COL - left)
    out["star_data_dots"] = dots(LINE_W - COL - len(" | Stars:") - len(out["star_data"]))
    # . Commits: ...... 1,234 | Followers: ..... 5
    out["commit_data_dots"] = dots(COL - len(". Commits:") - len(out["commit_data"]))
    out["follower_data_dots"] = dots(LINE_W - COL - len(" | Followers:") - len(out["follower_data"]))
    # . Lines of Code on GitHub: ... 12,345 ( 15,000++, 2,655-- )
    tail = len(" ( ") + len(out["loc_add"]) + len("++, ") + len(out["loc_del"]) + len("-- )")
    out["loc_data_dots"] = dots(LINE_W - len(". Lines of Code on GitHub:") - len(out["loc_data"]) - tail)
    return out


def daily_readme(birthday: datetime.datetime) -> str:
    diff = relativedelta.relativedelta(datetime.datetime.today(), birthday)

    def pl(n: int) -> str:
        return "s" if n != 1 else ""

    return "{} year{}, {} month{}, {} day{}{}".format(
        diff.years, pl(diff.years), diff.months, pl(diff.months), diff.days, pl(diff.days),
        " \U0001F382" if (diff.months == 0 and diff.days == 0) else "",
    )


# --------------------------------------------------------------------------- #
# GitHub GraphQL
# --------------------------------------------------------------------------- #
def headers() -> dict:
    token = os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("ERROR: set ACCESS_TOKEN atau GITHUB_TOKEN di environment.")
    return {"Authorization": f"bearer {token}"}


def gql(query: str, variables: dict) -> dict:
    r = requests.post(API, json={"query": query, "variables": variables}, headers=headers(), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"GraphQL {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(f"GraphQL: {json.dumps(data['errors'])[:200]}")
    return data["data"]


def user_info() -> dict:
    q = """query($login: String!) { user(login: $login) {
        id followers { totalCount }
        owned: repositories(ownerAffiliations: OWNER) { totalCount }
    } }"""
    u = gql(q, {"login": USER_NAME})["user"]
    return {"id": u["id"], "followers": u["followers"]["totalCount"], "repos": u["owned"]["totalCount"]}


def all_repos(affiliations: str) -> list[dict]:
    q = """query($login: String!, $cursor: String) { user(login: $login) {
        repositories(first: 100, after: $cursor, ownerAffiliations: %s) {
          pageInfo { hasNextPage endCursor }
          nodes { nameWithOwner stargazerCount
                  defaultBranchRef { target { ... on Commit { oid history { totalCount } } } } }
    } } }""" % affiliations
    repos, cursor = [], None
    while True:
        page = gql(q, {"login": USER_NAME, "cursor": cursor})["user"]["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return repos
        cursor = page["pageInfo"]["endCursor"]


def repo_loc(name: str, author_id: str) -> tuple[int, int, int]:
    """(additions, deletions, commits) milik author di branch utama repo."""
    owner, repo = name.split("/", 1)
    q = """query($owner: String!, $repo: String!, $id: ID!, $cursor: String) {
      repository(owner: $owner, name: $repo) { defaultBranchRef { target { ... on Commit {
        history(first: 100, after: $cursor, author: {id: $id}) {
          totalCount pageInfo { hasNextPage endCursor } nodes { additions deletions }
    } } } } } }"""
    add = dele = commits = 0
    cursor = None
    while True:
        ref = gql(q, {"owner": owner, "repo": repo, "id": author_id, "cursor": cursor})["repository"]["defaultBranchRef"]
        if not ref:
            return 0, 0, 0
        h = ref["target"]["history"]
        commits = h["totalCount"]
        for n in h["nodes"]:
            add += n["additions"]
            dele += n["deletions"]
        if not h["pageInfo"]["hasNextPage"]:
            return add, dele, commits
        cursor = h["pageInfo"]["endCursor"]


def loc_query(repos: list[dict], author_id: str) -> tuple[int, int, int]:
    """Total (+, -, commit) dengan cache: repo hanya dihitung ulang bila HEAD berubah."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / (hashlib.sha256(USER_NAME.encode()).hexdigest() + ".json")
    cache = json.loads(path.read_text()) if path.exists() else {}
    fresh = {}
    for r in repos:
        ref = r.get("defaultBranchRef")
        if not ref or not ref.get("target"):
            continue
        name, oid = r["nameWithOwner"], ref["target"]["oid"]
        h = hashlib.sha256(name.encode()).hexdigest()  # nama repo privat tidak bocor
        hit = cache.get(h)
        if hit and hit["oid"] == oid:
            fresh[h] = hit
            continue
        try:
            a, d, c = repo_loc(name, author_id)
        except RuntimeError as e:
            print(f"lewati {name}: {e}")
            continue
        fresh[h] = {"oid": oid, "additions": a, "deletions": d, "commits": c}
    path.write_text(json.dumps(fresh, indent=2, sort_keys=True) + "\n")
    add = sum(x["additions"] for x in fresh.values())
    dele = sum(x["deletions"] for x in fresh.values())
    commits = sum(x["commits"] for x in fresh.values())
    return add, dele, commits


# --------------------------------------------------------------------------- #
# SVG
# --------------------------------------------------------------------------- #
def find_and_replace(root, element_id: str, new_text: str) -> None:
    el = root.find(f".//*[@id='{element_id}']")
    if el is not None:
        el.text = new_text


def svg_overwrite(filename: Path, values: dict) -> None:
    tree = etree.parse(str(filename))
    root = tree.getroot()
    for k, text in layout(values).items():
        find_and_replace(root, k, text)
    tree.write(str(filename), encoding="utf-8", xml_declaration=True)


def collect() -> dict:
    info = user_info()
    contributed = all_repos("[OWNER, COLLABORATOR, ORGANIZATION_MEMBER]")
    owned = [r for r in contributed if r["nameWithOwner"].split("/")[0].lower() == USER_NAME.lower()]
    stars = sum(r["stargazerCount"] for r in owned)
    add, dele, commits = loc_query(contributed, info["id"])
    return {
        "age_data": daily_readme(BIRTHDAY),
        "repo_data": info["repos"],
        "contrib_data": len(contributed),
        "star_data": stars,
        "commit_data": commits,
        "follower_data": info["followers"],
        "loc_data": add - dele,
        "loc_add": add,
        "loc_del": dele,
    }


def main() -> None:
    values = collect()
    print(json.dumps({k: fmt(v) for k, v in values.items()}, ensure_ascii=False, indent=2))
    for name in ("dark_mode.svg", "light_mode.svg"):
        svg_overwrite(ROOT / name, values)
        print(f"diperbarui: {name}")


if __name__ == "__main__":
    main()

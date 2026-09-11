#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
finder/cli.py - The discovery agent's only tool.

The agent runs on a small model, so everything mechanical lives here and
only the judgment calls are left to it: is this category on topic, is this
article about a radical subject. Deduplication, the size-to-mode decision
and the maintenance-category filter are all decided in Python - but the
radical-topic call is not, because it needs to read a name, not match one.

Output is deliberately terse and machine-shaped - one record per line, no
emoji, no log noise, an END sentinel - because every token it prints comes
out of the agent's context budget.

    python -m finder.cli cat-list "Hadith scholars"
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
os.chdir(_REPO_ROOT)

import config
from finder import store, wiki

EXIT_OK = 0
EXIT_ERROR = 1


def _quiet() -> None:
    """Silence the pipeline's own INFO chatter - stdout is a contract here."""
    logging.getLogger("WikiTranslator").setLevel(logging.ERROR)


def _mode_for(size: int) -> str:
    return "trim" if size > config.TRIM_SIZE_THRESHOLD else "full"


def _category_state(data, name: str) -> str:
    """
    Where the agent stands with this category.

    SKIP - housekeeping or date bucket, never worth opening
    DONE - already worked through
    OPEN - already met, still has articles left
    NEW  - never seen
    """
    if wiki.is_maintenance_category(name):
        return "SKIP"
    rec = data.get("categories", {}).get(name)
    if rec is None:
        return "NEW"
    return "DONE" if rec.get("status") == "exhausted" else "OPEN"


def _record_candidates(data, names, source: str) -> None:
    """Remember topical categories we walked past, so they can be picked up later."""
    for name in names:
        if wiki.is_maintenance_category(name) or name in data.get("categories", {}):
            continue
        store.upsert_category(data, name, status="pending", source=source)


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_cat_list(args) -> int:
    category = wiki.normalize_category_name(args.category)
    members = wiki.fetch_category_members(category)

    data = store.load()
    known = store.known_titles(data)

    missing = {t: r for t, r in members.items() if not r["uz"]}
    fresh = [(t, r) for t, r in missing.items() if t not in known]
    fresh.sort(key=lambda kv: kv[1]["size"])

    # Written before the listing is printed: if the agent dies mid-thought,
    # the category is still on record as opened.
    store.upsert_category(
        data, category,
        status="in_progress",
        source=args.source,
        checked_at=store._now(),
        members=len(members),
        missing=len(missing),
    )
    store.save(data)

    print(f"CATEGORY {category} members={len(members)} missing={len(missing)} "
          f"new={len(fresh)} known={len(missing) - len(fresh)}")

    rows = fresh if not args.include_known else [(t, r) for t, r in missing.items()]
    for title, rec in rows[:args.limit]:
        print(f"{rec['size']}\t{_mode_for(rec['size'])}\t{title}")

    if len(rows) > args.limit:
        print(f"MORE {len(rows) - args.limit}")
    print("END")
    return EXIT_OK


def cmd_art_cats(args) -> int:
    cats = wiki.fetch_article_categories(args.title)
    if not cats:
        print(f"MISSING {args.title}")
        print("END")
        return EXIT_OK

    data = store.load()
    # Label first: _record_candidates would otherwise make every category
    # it just wrote read back as already known.
    labels = [(_category_state(data, name), name) for name in cats]
    _record_candidates(data, cats, source=args.title)
    store.save(data)

    for state, name in labels:
        print(f"{state}\t{name}")
    print("END")
    return EXIT_OK


def cmd_cat_tree(args) -> int:
    category = wiki.normalize_category_name(args.category)
    parents = wiki.fetch_category_parents(category)
    subs = wiki.fetch_subcategories(category)

    data = store.load()
    labels = {name: _category_state(data, name) for name in parents + subs}
    _record_candidates(data, parents + subs, source=category)
    store.save(data)

    for name in parents:
        print(f"PARENT\t{labels[name]}\t{name}")
    for name in subs:
        print(f"SUB\t{labels[name]}\t{name}")
    print("END")
    return EXIT_OK


def cmd_screen(args) -> int:
    """
    Show each candidate's own categories, so the agent can judge from them.

    This used to answer RISK or CLEAR from a keyword list. It does not any
    more: the list could not distinguish a movement from its critics or its
    victims, and every fix it took added another pattern. Reading the names
    is the model's job; the mechanical part is fetching them and dropping
    the date and cleanup buckets.
    """
    cats = wiki.fetch_titles_categories(args.titles)

    for title in args.titles:
        topical = wiki.topical_categories(cats.get(title, []))
        names = [wiki.strip_category_prefix(c) for c in topical]
        print(f"{title}\t" + ("|".join(names) if names else "(none)"))
    print("END")
    return EXIT_OK


def cmd_queue_add(args) -> int:
    info = wiki.fetch_titles_info(args.titles)
    data = store.load()
    category = wiki.normalize_category_name(args.category) if args.category else None
    added = 0

    for title in args.titles:
        rec = info.get(title)
        if rec is None or rec["missing"]:
            print(f"MISSING\t{title}")
            continue
        if rec["uz"]:
            print(f"HASUZ\t{title}\tuz={rec['uz']}")
            continue

        size = rec["size"]
        mode = args.mode if args.mode != "auto" else _mode_for(size)
        outcome, status = store.upsert_article(
            data, title,
            status="queued", mode=mode, size=size,
            category=category, url=wiki.make_url(title),
        )
        if outcome == "dup":
            print(f"DUP\t{title}\tstatus={status}")
        else:
            added += 1
            print(f"ADDED\t{title}\tmode={mode}\tsize={size}")

    if category and added:
        cat = store.upsert_category(data, category)
        cat["queued"] = cat.get("queued", 0) + added

    store.save(data)
    print("END")
    return EXIT_OK


def cmd_reject(args) -> int:
    data = store.load()
    rejected = 0

    for title in args.titles:
        outcome, status = store.upsert_article(
            data, title,
            status="rejected", reject_reason=args.reason,
            url=wiki.make_url(title),
        )
        if outcome == "added":
            rejected += 1
            print(f"REJECTED\t{title}")
        elif status == "queued":
            # A second look overrules the first: something already queued can
            # still be pulled back out. Anything translated or published has
            # left the queue and is the human's to undo.
            store.mark(data, title, "rejected", reject_reason=args.reason)
            rejected += 1
            print(f"REJECTED\t{title}\twas=queued")
        else:
            print(f"DUP\t{title}\tstatus={status}")

    if args.category and rejected:
        cat = store.upsert_category(data, wiki.normalize_category_name(args.category))
        cat["rejected"] = cat.get("rejected", 0) + rejected

    store.save(data)
    print("END")
    return EXIT_OK


def cmd_requeue(args) -> int:
    """
    Put rejected articles back in the queue.

    The mirror of `reject` pulling a queued article out. A rejection is a
    judgment, and judgments get revised - when the screening rules change, or
    when the maintainer disagrees with one. Only a rejected article can come
    back: anything translated or published never left.
    """
    info = wiki.fetch_titles_info(args.titles)
    data = store.load()
    category = wiki.normalize_category_name(args.category) if args.category else None

    for title in args.titles:
        rec = data.get("articles", {}).get(title)
        if rec is None:
            print(f"UNKNOWN\t{title}")
            continue
        if rec.get("status") != "rejected":
            print(f"SKIP\t{title}\tstatus={rec.get('status')}")
            continue

        size = (info.get(title) or {}).get("size") or rec.get("size") or 0
        mode = _mode_for(size)
        store.mark(data, title, "queued", mode=mode, size=size,
                   category=category or rec.get("category"))
        # The old reason would otherwise sit on a queued article and read as
        # though it still applied.
        rec["reject_reason"] = None
        print(f"REQUEUED\t{title}\tmode={mode}\tsize={size}")

    store.save(data)
    print("END")
    return EXIT_OK


def cmd_cat_done(args) -> int:
    category = wiki.normalize_category_name(args.category)
    data = store.load()
    store.upsert_category(data, category, status="exhausted", note=args.note)
    store.save(data)
    print(f"DONE\t{category}")
    print("END")
    return EXIT_OK


def cmd_status(args) -> int:
    data = store.load()
    stats = data.get("stats", {})
    print(" ".join(
        f"{s.upper()} {stats.get(s, 0)}" for s in store.ARTICLE_STATUSES
    ))

    cats = data.get("categories", {})
    counts = {s: 0 for s in store.CATEGORY_STATUSES}
    for rec in cats.values():
        status = rec.get("status")
        if status in counts:
            counts[status] += 1
    print("CATS " + " ".join(f"{k}={v}" for k, v in counts.items()))

    current = store.current_category(data)
    print(f"CURRENT\t{current}" if current else "CURRENT\tnone")

    for name in store.pending_categories(data)[:args.pending]:
        print(f"PENDING\t{name}")
    print("END")
    return EXIT_OK


def cmd_next(args) -> int:
    data = store.load()
    rows = store.next_queued(data, args.number)

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return EXIT_OK

    for row in rows:
        print(f"{row['size']}\t{row['mode']}\t{row['title']}")
    print("END")
    return EXIT_OK


# ── argument parsing ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    # Help text and the ERROR line are written in English, against the
    # project's Uzbek-for-user-facing-output convention: this interface is
    # read by the discovery agent, which runs on a small model that handles
    # English far better than Uzbek.
    parser = argparse.ArgumentParser(
        prog="finder",
        description="Find articles for the translation queue.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("cat-list", help="Articles in a category that are missing from uz.wiki")
    p.add_argument("category")
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--source", default="seed",
                   help="How this category was reached (navigation trail)")
    p.add_argument("--include-known", action="store_true")
    p.set_defaults(func=cmd_cat_list)

    p = sub.add_parser("art-cats", help="An article's categories")
    p.add_argument("title")
    p.set_defaults(func=cmd_art_cats)

    p = sub.add_parser("cat-tree", help="A category's parent and child categories")
    p.add_argument("category")
    p.set_defaults(func=cmd_cat_tree)

    p = sub.add_parser("screen", help="Show each candidate's own categories")
    p.add_argument("titles", nargs="+")
    p.set_defaults(func=cmd_screen)

    p = sub.add_parser("queue-add", help="Add articles to the queue")
    p.add_argument("titles", nargs="+")
    p.add_argument("--category")
    p.add_argument("--mode", choices=["auto", "full", "trim"], default="auto")
    p.set_defaults(func=cmd_queue_add)

    p = sub.add_parser("reject", help="Reject articles, with a reason")
    p.add_argument("titles", nargs="+")
    p.add_argument("--reason", required=True)
    p.add_argument("--category")
    p.set_defaults(func=cmd_reject)

    p = sub.add_parser("requeue", help="Put rejected articles back in the queue")
    p.add_argument("titles", nargs="+")
    p.add_argument("--category")
    p.set_defaults(func=cmd_requeue)

    p = sub.add_parser("cat-done", help="Mark a category as finished")
    p.add_argument("category")
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_cat_done)

    p = sub.add_parser("status", help="State of the queue")
    p.add_argument("--pending", type=int, default=5)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("next", help="The next articles in the queue")
    p.add_argument("-n", "--number", type=int, default=config.DAILY_BATCH_SIZE)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_next)

    return parser


def main(argv=None) -> int:
    _quiet()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:
        print(f"ERROR {e}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())

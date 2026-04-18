"""Collect Chromium/Firefox parity + performance baseline metrics.

Usage:
  .venv/bin/python examples/parity_baseline.py \
      --engines chromium firefox \
      --urls https://example.com https://www.wikipedia.org \
      --out /tmp/anxbrowser-baseline.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any

from playwright.async_api import async_playwright


@dataclass
class StepMetric:
    step: str
    ms: float
    ok: bool
    note: str = ""


@dataclass
class PageMetric:
    engine: str
    url: str
    final_url: str
    title: str
    screenshot_bytes: int
    visible_text_chars: int
    steps: list[StepMetric]


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


async def _measure_page(engine: str, browser: Any, url: str) -> PageMetric:
    context = await browser.new_context(viewport={"width": 1280, "height": 800})
    page = await context.new_page()

    steps: list[StepMetric] = []

    t0 = _now_ms()
    ok = True
    note = ""
    try:
        await page.goto(url, wait_until="load")
    except Exception as exc:
        ok = False
        note = str(exc)
    steps.append(StepMetric(step="navigate", ms=_now_ms() - t0, ok=ok, note=note))

    title = ""
    final_url = page.url
    if ok:
        t1 = _now_ms()
        try:
            title = await page.title()
            steps.append(StepMetric(step="title", ms=_now_ms() - t1, ok=True))
        except Exception as exc:
            steps.append(StepMetric(step="title", ms=_now_ms() - t1, ok=False, note=str(exc)))

    visible_text = ""
    if ok:
        t2 = _now_ms()
        try:
            visible_text = await page.evaluate(
                """() => {
                    const t = document.body ? document.body.innerText : "";
                    return t.replace(/\s+/g, " ").trim().slice(0, 4096);
                }"""
            )
            steps.append(StepMetric(step="observe_text", ms=_now_ms() - t2, ok=True))
        except Exception as exc:
            steps.append(StepMetric(step="observe_text", ms=_now_ms() - t2, ok=False, note=str(exc)))

    screenshot_bytes = 0
    if ok:
        t3 = _now_ms()
        try:
            shot = await page.screenshot(type="jpeg", quality=60, full_page=False)
            screenshot_bytes = len(shot)
            steps.append(StepMetric(step="screenshot", ms=_now_ms() - t3, ok=True))
        except Exception as exc:
            steps.append(StepMetric(step="screenshot", ms=_now_ms() - t3, ok=False, note=str(exc)))

    await context.close()
    return PageMetric(
        engine=engine,
        url=url,
        final_url=final_url,
        title=title,
        screenshot_bytes=screenshot_bytes,
        visible_text_chars=len(visible_text),
        steps=steps,
    )


async def run(engines: list[str], urls: list[str]) -> dict[str, Any]:
    results: list[PageMetric] = []
    async with async_playwright() as p:
        for engine in engines:
            launcher = getattr(p, engine)
            browser = await launcher.launch(headless=True)
            try:
                for url in urls:
                    results.append(await _measure_page(engine, browser, url))
            finally:
                await browser.close()

    payload = [asdict(r) for r in results]

    by_engine: dict[str, dict[str, Any]] = {}
    for engine in engines:
        rows = [r for r in results if r.engine == engine]
        nav = [s.ms for r in rows for s in r.steps if s.step == "navigate" and s.ok]
        obs = [s.ms for r in rows for s in r.steps if s.step == "observe_text" and s.ok]
        by_engine[engine] = {
            "pages": len(rows),
            "navigate_ms_avg": round(mean(nav), 2) if nav else None,
            "observe_ms_avg": round(mean(obs), 2) if obs else None,
            "avg_screenshot_bytes": round(mean([r.screenshot_bytes for r in rows]), 2)
            if rows
            else None,
        }

    return {
        "meta": {
            "engines": engines,
            "urls": urls,
            "generated_at_epoch_s": time.time(),
        },
        "summary": by_engine,
        "results": payload,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines", nargs="+", default=["chromium", "firefox"])
    ap.add_argument(
        "--urls",
        nargs="+",
        default=["https://example.com", "https://www.wikipedia.org"],
    )
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    for engine in args.engines:
        if engine not in {"chromium", "firefox"}:
            raise SystemExit(f"unsupported engine: {engine}")
    data = asyncio.run(run(args.engines, args.urls))
    text = json.dumps(data, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(args.out)
    else:
        print(text)


if __name__ == "__main__":
    main()

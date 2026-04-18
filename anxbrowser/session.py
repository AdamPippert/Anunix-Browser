"""Session manager.

One BrowserSession wraps one Playwright BrowserContext and exactly one active
Page. The session owns an EventBus, a policy, and a link to an Anunix Cell.

Playwright is imported lazily so that the test suite and stub scripts can
import anxbrowser modules without pulling Chromium into process memory.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .bridge import AnunixBridge
from .events import EventBus

log = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    session_id: str
    cell_id: Optional[str]
    namespace: str
    created_at: float
    current_url: str = "about:blank"
    driver: Optional[str] = None
    subscribers: int = 0


class BrowserSession:
    """A single browser session."""

    def __init__(
        self,
        session_id: str,
        context: Any,
        page: Any,
        bridge: AnunixBridge,
        namespace: str,
        cell_id: Optional[str],
    ) -> None:
        self.session_id = session_id
        self._context = context
        self._page = page
        self._bridge = bridge
        self.namespace = namespace
        self.cell_id = cell_id
        self.created_at = time.time()
        self.bus = EventBus()
        self.driver: Optional[str] = None
        self._closed = False
        self._page.on("console", self._on_console)
        self._page.on("pageerror", self._on_page_error)

    # --- Introspection ---------------------------------------------------

    @property
    def closed(self) -> bool:
        return self._closed

    def info(self) -> SessionInfo:
        return SessionInfo(
            session_id=self.session_id,
            cell_id=self.cell_id,
            namespace=self.namespace,
            created_at=self.created_at,
            current_url=self._page.url if self._page else "about:blank",
            driver=self.driver,
            subscribers=self.bus.subscriber_count,
        )

    # --- Core actions ----------------------------------------------------

    async def navigate(self, url: str, wait_until: str = "load") -> Dict[str, Any]:
        response = await self._page.goto(url, wait_until=wait_until)
        title = await self._page.title()
        status = response.status if response else 0
        html = await self._page.content()
        bridge_result = await self._bridge.store_page_as_state_object(
            session_id=self.session_id,
            ns_path=f"{self.namespace}/{self.session_id}/pages",
            url=self._page.url,
            title=title,
            html=html,
        )
        page_so = (
            bridge_result.data.get("state_object")
            if bridge_result.ok and bridge_result.data
            else None
        )
        event = await self.bus.publish(
            "navigated",
            {
                "url": self._page.url,
                "title": title,
                "status": status,
                "page_state_object": page_so,
            },
        )
        return {
            "event_id": event.seq,
            "status": status,
            "url": self._page.url,
            "title": title,
            "page_state_object": page_so,
        }

    async def observe(
        self,
        include_screenshot: bool = True,
        include_html: bool = False,
        text_only: bool = True,
    ) -> Dict[str, Any]:
        title = await self._page.title()
        url = self._page.url
        visible_text = ""
        if text_only:
            visible_text = await self._page.evaluate(
                "() => document.body ? document.body.innerText : ''"
            )
            visible_text = " ".join(visible_text.split())[:4096]
        html = await self._page.content() if include_html else None
        shot_b64 = None
        shot_bytes = None
        if include_screenshot:
            shot_bytes = await self._page.screenshot(type="png", full_page=False)
            shot_b64 = base64.b64encode(shot_bytes).decode("ascii")
        bridge_result = await self._bridge.store_page_as_state_object(
            session_id=self.session_id,
            ns_path=f"{self.namespace}/{self.session_id}/observations",
            url=url,
            title=title,
            html=html or "",
            screenshot_png=shot_bytes,
        )
        page_so = (
            bridge_result.data.get("state_object")
            if bridge_result.ok and bridge_result.data
            else None
        )
        event = await self.bus.publish(
            "observed",
            {"url": url, "title": title, "page_state_object": page_so},
        )
        result = {
            "event_id": event.seq,
            "url": url,
            "title": title,
            "visible_text": visible_text,
            "page_state_object": page_so,
        }
        if shot_b64:
            result["screenshot_b64"] = shot_b64
            result["screenshot_mime"] = "image/png"
        if html is not None:
            result["html"] = html
        return result

    async def click(
        self, selector: str, button: str = "left", timeout_ms: int = 5000
    ) -> Dict[str, Any]:
        await self._page.click(selector, button=button, timeout=timeout_ms)
        await self._bridge.record_action(
            self.session_id, "click", {"selector": selector, "button": button}
        )
        event = await self.bus.publish("clicked", {"selector": selector})
        return {"event_id": event.seq, "clicked": True}

    async def type_text(
        self,
        text: str,
        selector: Optional[str] = None,
        press_enter: bool = False,
    ) -> Dict[str, Any]:
        if selector:
            await self._page.fill(selector, text)
        else:
            await self._page.keyboard.type(text)
        if press_enter:
            await self._page.keyboard.press("Enter")
        await self._bridge.record_action(
            self.session_id, "type", {"selector": selector, "length": len(text)}
        )
        event = await self.bus.publish(
            "typed", {"selector": selector, "length": len(text)}
        )
        return {"event_id": event.seq, "typed": len(text)}

    async def scroll(
        self,
        dx: int = 0,
        dy: int = 0,
        to_selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        if to_selector:
            await self._page.eval_on_selector(
                to_selector, "el => el.scrollIntoView({block: 'center'})"
            )
            payload = {"to_selector": to_selector}
        else:
            await self._page.evaluate(
                "({x, y}) => window.scrollBy(x, y)", {"x": dx, "y": dy}
            )
            payload = {"dx": dx, "dy": dy}
        event = await self.bus.publish("scrolled", payload)
        return {"event_id": event.seq, **payload}

    async def wait_for(self, selector: str, timeout_ms: int = 10000) -> Dict[str, Any]:
        await self._page.wait_for_selector(selector, timeout=timeout_ms)
        event = await self.bus.publish("waited", {"selector": selector})
        return {"event_id": event.seq, "selector": selector}

    async def eval_js(self, expression: str) -> Dict[str, Any]:
        result = await self._page.evaluate(expression)
        event = await self.bus.publish(
            "evaluated", {"expression_len": len(expression)}
        )
        return {
            "event_id": event.seq,
            "result": result,
            "type": type(result).__name__,
        }

    async def frame_screenshot(self) -> Optional[bytes]:
        if self._closed:
            return None
        try:
            return await self._page.screenshot(type="jpeg", quality=60, full_page=False)
        except Exception as exc:
            log.debug("frame screenshot failed: %s", exc)
            return None

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._page.close()
        except Exception:
            pass
        try:
            await self._context.close()
        except Exception:
            pass
        await self.bus.publish("terminal", {"reason": "closed"})

    # --- Event plumbing --------------------------------------------------

    def _on_console(self, msg: Any) -> None:
        try:
            level = getattr(msg, "type", "log")
            text = getattr(msg, "text", str(msg))
        except Exception:
            level, text = "log", ""
        asyncio.create_task(
            self.bus.publish("console", {"level": str(level), "text": str(text)[:1024]})
        )

    def _on_page_error(self, err: Any) -> None:
        asyncio.create_task(
            self.bus.publish(
                "page_error",
                {"message": str(err)[:512]},
            )
        )


class SessionManager:
    """Owns Playwright and the set of live sessions."""

    def __init__(self, bridge: AnunixBridge, headless_default: bool = True) -> None:
        self._bridge = bridge
        self._headless_default = headless_default
        self._sessions: Dict[str, BrowserSession] = {}
        self._playwright: Any = None
        self._browser: Any = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            log.warning(
                "playwright not installed; session creation will fail. "
                "run `make deps` to install."
            )
            return
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless_default
            )
            log.info(
                "playwright started, chromium launched (headless=%s)",
                self._headless_default,
            )
        except Exception as exc:
            log.warning(
                "playwright failed to start (%s); session creation will fail. "
                "run `python -m playwright install chromium`.",
                exc,
            )
            self._playwright = None
            self._browser = None

    async def stop(self) -> None:
        for sid in list(self._sessions):
            try:
                await self.close_session(sid)
            except Exception:
                pass
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def create_session(
        self,
        headless: bool = True,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
        cell_id: Optional[str] = None,
        namespace: str = "/sessions",
    ) -> BrowserSession:
        async with self._lock:
            if self._browser is None:
                raise RuntimeError(
                    "browser engine unavailable; install playwright with `make deps`"
                )
            session_id = f"sess_{uuid.uuid4().hex[:12]}"
            vp = viewport or {"width": 1280, "height": 800}
            context = await self._browser.new_context(
                viewport=vp, user_agent=user_agent
            )
            page = await context.new_page()
            bridge_result = await self._bridge.bind_session_to_cell(
                session_id=session_id, cell_id=cell_id
            )
            effective_cell = cell_id
            if bridge_result.ok and bridge_result.data:
                effective_cell = (
                    bridge_result.data.get("cell_id") or effective_cell
                )
            session = BrowserSession(
                session_id=session_id,
                context=context,
                page=page,
                bridge=self._bridge,
                namespace=namespace,
                cell_id=effective_cell,
            )
            self._sessions[session_id] = session
            await session.bus.publish(
                "session_created",
                {
                    "session_id": session_id,
                    "cell_id": effective_cell,
                    "created_at": session.created_at,
                },
            )
            return session

    def get(self, session_id: str) -> Optional[BrowserSession]:
        return self._sessions.get(session_id)

    def list(self) -> List[SessionInfo]:
        return [s.info() for s in self._sessions.values()]

    async def close_session(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if not session:
            return False
        await session.close()
        return True

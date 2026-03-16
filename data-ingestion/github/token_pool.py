"""
GitHub PAT Token Pool
=====================
Round-robin rotation across multiple Personal Access Tokens to stay
well below the 5,000 req/hr/token limit.

Usage
─────
    pool = GitHubTokenPool.from_env()
    headers = pool.next_headers()   # rotate automatically

Environment variables
──────────────────────
    GITHUB_TOKEN            — primary token (always required)
    GITHUB_TOKEN_1 … _9    — additional tokens (optional)

The pool pauses automatically when a token is rate-limited:
it reads X-RateLimit-Reset, sleeps until the window resets, then
continues. With 5 tokens you have an effective limit of 25,000 req/hr.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from itertools import cycle
from typing import Dict, Iterator, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# GitHub REST rate limit endpoint
_RATE_LIMIT_URL = "https://api.github.com/rate_limit"


@dataclass
class TokenSlot:
    """One PAT with its current rate-limit state."""
    token:           str
    remaining:       int  = 5000
    reset_at_epoch:  int  = 0   # Unix timestamp when the window resets
    is_exhausted:    bool = False

    @property
    def seconds_until_reset(self) -> int:
        return max(0, self.reset_at_epoch - int(time.time()))

    def mark_exhausted(self, reset_at: int) -> None:
        self.is_exhausted = True
        self.reset_at_epoch = reset_at
        logger.warning("Token …%s exhausted — pausing until %s", self.token[-4:], reset_at)

    def refresh(self, remaining: int, reset_at: int) -> None:
        self.remaining = remaining
        self.reset_at_epoch = reset_at
        self.is_exhausted = remaining == 0


class GitHubTokenPool:
    """
    Thread-safe async token pool with exhaustion detection and
    automatic wait-and-retry on rate-limit responses.
    """

    def __init__(self, tokens: List[str]) -> None:
        if not tokens:
            raise ValueError("GitHubTokenPool requires at least one token")
        self._slots: List[TokenSlot] = [TokenSlot(t) for t in tokens]
        self._cycle: Iterator[TokenSlot] = cycle(self._slots)
        self._lock = asyncio.Lock()
        logger.info("TokenPool initialised with %d token(s)", len(self._slots))

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_env(cls) -> "GitHubTokenPool":
        """Load tokens from GITHUB_TOKEN + GITHUB_TOKEN_1..9 env vars."""
        tokens: List[str] = []
        primary = os.getenv("GITHUB_TOKEN", "")
        if primary:
            tokens.append(primary)
        for i in range(1, 10):
            extra = os.getenv(f"GITHUB_TOKEN_{i}", "")
            if extra:
                tokens.append(extra)
        if not tokens:
            raise EnvironmentError(
                "No GitHub tokens found. Set GITHUB_TOKEN or GITHUB_TOKEN_1…9."
            )
        return cls(tokens)

    # ── Public API ────────────────────────────────────────────────────────────

    async def next_headers(self) -> Dict[str, str]:
        """
        Return Authorization headers for the next available token.
        Blocks (with asyncio.sleep) if all tokens are exhausted.
        """
        async with self._lock:
            slot = await self._pick_available_slot()
        return {
            "Authorization": f"Bearer {slot.token}",
            "Accept":        "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def handle_rate_limit_response(
        self,
        headers: Dict[str, str],
        token: str,
    ) -> None:
        """
        Call this when a 403/429 with X-RateLimit-Remaining: 0 is received.
        Marks the slot as exhausted so next_headers skips it.
        """
        reset_at = int(headers.get("X-RateLimit-Reset", time.time() + 60))
        for slot in self._slots:
            if slot.token == token:
                slot.mark_exhausted(reset_at)
                break

    def update_from_response_headers(
        self,
        headers: Dict[str, str],
        token: str,
    ) -> None:
        """Update remaining/reset from every successful response."""
        remaining = int(headers.get("X-RateLimit-Remaining", 5000))
        reset_at  = int(headers.get("X-RateLimit-Reset", time.time() + 3600))
        for slot in self._slots:
            if slot.token == token:
                slot.refresh(remaining, reset_at)
                break

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _pick_available_slot(self) -> TokenSlot:
        """
        Iterate the cycle until we find an available slot.
        If all slots are exhausted, sleep until the earliest reset.
        """
        checked = 0
        while True:
            slot = next(self._cycle)
            if not slot.is_exhausted:
                return slot

            checked += 1
            if checked >= len(self._slots):
                # All exhausted — sleep until the soonest reset
                soonest = min(s.seconds_until_reset for s in self._slots)
                wait = max(1, soonest + 2)   # +2 s buffer
                logger.warning(
                    "All %d tokens exhausted. Sleeping %ds.", len(self._slots), wait
                )
                await asyncio.sleep(wait)
                # Un-exhaust slots whose window has passed
                now = int(time.time())
                for s in self._slots:
                    if s.is_exhausted and s.reset_at_epoch <= now:
                        s.is_exhausted = False
                        s.remaining = 5000
                checked = 0

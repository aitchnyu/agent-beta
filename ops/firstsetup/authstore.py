"""authstore — debian's pi credential store as a class.

pi ALWAYS runs as debian on this machine — root in an unprivileged
container cannot write into debian's mapped home, so every read/write
rides ``sudo -u debian -H``. Writes are COMPACT single-line JSON: the
read parses the last line, and a pretty-printed body would round-trip
as {} (wiping every other provider).
"""

from __future__ import annotations

import asyncio
import json


class AuthStore:
    """Read/write pi's credential store for a fixed path."""

    def __init__(self, store_path: str) -> None:
        self.store_path = store_path

    async def read(self) -> dict[str, dict[str, object]]:
        """Read the whole store; a missing store reads as {} (fresh).

        Only the EXPECTED fresh state (cat: "No such file or directory")
        is empty. Any other failure raises: a silently-empty store would
        make the next write clobber every credential that couldn't be
        read.
        """
        proc = await asyncio.create_subprocess_exec(
            "sudo",
            "-u",
            "debian",
            "-H",
            "cat",
            self.store_path,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            stderr_text = err.decode(errors="replace")
            if "No such file or directory" in stderr_text:
                return {}  # fresh machine — pi creates the store on login
            message = f"credential store read failed: {stderr_text.strip()[:200]}"
            raise RuntimeError(message)
        text = out.decode(errors="replace").strip()
        if not text:
            return {}
        store: dict[str, dict[str, object]] = json.loads(text.splitlines()[-1])
        return store

    async def write(self, store: dict[str, dict[str, object]]) -> None:
        """Write the store as debian (0600 via umask); raises on failure."""
        proc = await asyncio.create_subprocess_exec(
            "sudo",
            "-u",
            "debian",
            "-H",
            "bash",
            "-c",
            f"mkdir -p $(dirname {self.store_path}); umask 077; cat > {self.store_path}",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        _out, _err = await proc.communicate(json.dumps(store).encode())
        if proc.returncode != 0:
            message = f"credential store write failed (rc={proc.returncode})"
            raise RuntimeError(message)

    async def set_credential(self, provider_id: str, credential: dict[str, object]) -> None:
        """Fold one credential into the store, never clobbering others."""
        store = await self.read()
        store[provider_id] = credential
        await self.write(store)

"""Check, provision, and clean up the production writer using the DigitalOcean API."""

import argparse
import ipaddress
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

API = "https://api.digitalocean.com/v2"


class ApiError(RuntimeError):
    """Retain the provider's status and error without exposing request credentials."""

    def __init__(self, status, message):
        """Record a safe provider diagnostic."""
        self.status = status
        super().__init__(f"DigitalOcean HTTP {status}: {message}")


class NoRedirect(HTTPRedirectHandler):
    """Do not forward a bearer token through API redirects."""

    def redirect_request(self, *args, **kwargs):
        """Reject redirects instead of forwarding the authorization header."""


class DigitalOcean:
    """Use JSON API responses directly; creation requests are never retried."""

    def __init__(self, token):
        """Configure an authenticated, timeout-bounded API client."""
        if not token:
            raise ValueError("Missing DigitalOcean token")
        self.token = token
        self.opener = build_opener(NoRedirect())

    def request(self, method, path, payload=None, *, missing_ok=False, attempts=3):
        """Retry safe requests, retaining HTTP failures and accepting explicit 404s."""
        url = path if path.startswith(API + "/") else API + path
        if urlsplit(url)[:2] != urlsplit(API)[:2] or not urlsplit(url).path.startswith("/v2/"):
            raise ValueError("Invalid DigitalOcean API URL")
        request = Request(
            url,
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            data=json.dumps(payload).encode() if payload is not None else None,
        )
        for attempt in range(attempts):
            try:
                with self.opener.open(request, timeout=15) as response:
                    content = response.read()
                result = json.loads(content) if content else {}
                if not isinstance(result, dict):
                    raise TypeError("Invalid DigitalOcean response")
                return result
            except HTTPError as error:
                with error:
                    if missing_ok and error.code == 404:
                        return None
                    try:
                        details = json.loads(error.read())
                        message = details.get("message", error.reason)
                    except (ValueError, AttributeError):
                        message = error.reason
                    failure = ApiError(error.code, str(message).replace(self.token, "***"))
                    retry = error.code in (429, 500, 502, 503, 504)
                    delay = error.headers.get("Retry-After", str(5 * (attempt + 1)))
                    delay = float(delay) if delay.isdecimal() else 5 * (attempt + 1)
            except (URLError, TimeoutError) as error:
                failure, retry, delay = error, True, 5 * (attempt + 1)
            if method == "POST" or not retry or attempt == attempts - 1 or delay > 30:
                raise failure
            time.sleep(delay)

    def list(self, path, field):
        """Read every inventory page without following links outside this endpoint."""
        results, seen = [], set()
        next_page = path + ("&" if "?" in path else "?") + "per_page=200"
        while next_page:
            if next_page in seen:
                raise ValueError("Repeated DigitalOcean pagination URL")
            seen.add(next_page)
            response = self.request("GET", next_page)
            items = response.get(field)
            if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                raise ValueError(f"Invalid DigitalOcean {field} inventory")
            results.extend(items)
            next_page = response.get("links", {}).get("pages", {}).get("next")
            if next_page and (
                not isinstance(next_page, str)
                or urlsplit(next_page)[:2] != urlsplit(API)[:2]
                or urlsplit(next_page).path != urlsplit(API + path).path
            ):
                raise ValueError("Invalid DigitalOcean pagination URL")
        return results


def identity(record):
    """Reject malformed resource IDs before storing or deleting them."""
    value = record.get("id") if isinstance(record, dict) else None
    if type(value) is not int or value <= 0:
        raise ValueError("Expected a positive DigitalOcean resource ID")
    return value


def output(name, value):
    """Write a validated decision or resource ID to the workflow output."""
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        encoded = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
        stream.write(f"{name}={encoded}\n")


def environment():
    """Use the current workflow token for public upstream reads in both containers."""
    lines = os.environ["UPDATELOOP_ENV"].splitlines()
    token = os.environ.get("GH_TOKEN")
    if token:
        lines = [
            line for line in lines if line.partition("=")[0].strip() != "ARKWAIFU_GITHUB_TOKEN"
        ]
        lines.append(f"ARKWAIFU_GITHUB_TOKEN={token}")
    return ("\n".join(lines) + "\n").encode()


def command(arguments, *, input=None, capture=False, quiet=False, log=None):
    """Run Docker or SSH without a local shell; keep long logs file-backed."""
    if log is None:
        result = subprocess.run(
            arguments,
            input=input,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.DEVNULL if quiet else None,
            check=True,
        )
        return result.stdout or b""
    with Path(log).open("wb") as stream:
        process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            for line in process.stdout:
                stream.write(line)
                stream.flush()
                print(line.decode("utf-8", errors="replace"), end="", flush=True)
            if process.wait() != 0:
                raise subprocess.CalledProcessError(process.returncode, arguments)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
    return b""


def logs():
    """Keep workflow artifacts beneath the runner's temporary directory."""
    directory = Path(os.environ["RUNNER_TEMP"]) / "updateloop-logs"
    directory.mkdir(exist_ok=True)
    return directory


def check():
    """Publish a decision only after a successful read-only preflight."""
    directory = logs()
    cache = Path(os.environ["RUNNER_TEMP"]) / "updateloop-database-cache"
    cache.mkdir(exist_ok=True)
    owner = cache.stat()
    with tempfile.TemporaryDirectory(dir=os.environ["RUNNER_TEMP"], prefix="updateloop-") as work:
        env_file = Path(work) / ".env.prod"
        env_file.write_bytes(environment())
        env_file.chmod(0o600)
        image = os.environ["UPDATELOOP_IMAGE"]
        command(
            [
                "docker",
                "login",
                "ghcr.io",
                "--username",
                os.environ["GITHUB_ACTOR"],
                "--password-stdin",
            ],
            input=os.environ["GH_TOKEN"].encode(),
        )
        command(["docker", "pull", image])
        try:
            decision = command(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--user",
                    f"{owner.st_uid}:{owner.st_gid}",
                    "--env-file",
                    str(env_file),
                    "--volume",
                    f"{cache.resolve()}:/preflight-cache",
                    image,
                    "check",
                    "--database-cache-dir",
                    "/preflight-cache",
                ],
                capture=True,
            )
        except subprocess.CalledProcessError as error:
            (directory / "preflight.json").write_bytes(error.stdout or b"")
            raise
        (directory / "preflight.json").write_bytes(decision)
        payload = json.loads(decision)
        needed = payload.get("update_needed") if isinstance(payload, dict) else None
        if type(needed) is not bool:
            raise ValueError("Invalid preflight decision")
        if "database_cache_key" not in payload:
            raise ValueError("Missing preflight database cache key; publish the updated image")
        cache_key = payload["database_cache_key"]
        if cache_key is not None:
            if not isinstance(cache_key, str) or not re.fullmatch(
                "[0-9a-f]{64}-[0-9a-f]{32}", cache_key
            ):
                raise ValueError("Invalid preflight database cache key")
            output("database_cache_key", f"updateloop-preflight-db-v1-{cache_key}")
        output("update_needed", needed)


class Coordinator:
    """Own one invocation's resources while respecting other live writers."""

    def __init__(self, api):
        """Load this workflow invocation's name, tag, and known resource IDs."""
        self.api = api
        self.name = os.environ["DROPLET_NAME"]
        self.tag = os.environ["DROPLET_TAG"]
        self.ids = json.loads(os.environ.get("DROPLET_IDS") or "[]")
        if not isinstance(self.ids, list):
            raise TypeError("Invalid known Droplet IDs")
        for value in self.ids:
            identity({"id": value})

    def droplets(self):
        """List all writers carrying this repository's tag."""
        return self.api.list("/droplets?" + urlencode({"tag_name": self.tag}), "droplets")

    def destroy(self, resource_id):
        """Retry deletion until the resource itself returns 404."""
        identity({"id": resource_id})
        path = f"/droplets/{resource_id}"
        for attempt in range(12):
            try:
                if self.api.request("GET", path, missing_ok=True, attempts=1) is None:
                    print(f"Confirmed Droplet {resource_id} is deleted (API returned 404).")
                    return
                self.api.request("DELETE", path, missing_ok=True, attempts=1)
            except (ApiError, URLError, TimeoutError) as error:
                if isinstance(error, ApiError) and error.status not in (429, 500, 502, 503, 504):
                    raise
            if attempt < 11:
                time.sleep(5)
        raise RuntimeError(f"Could not confirm deletion of Droplet {resource_id}")

    def delete_keys(self, name):
        """Delete this run's keys, accepting keys already deleted by another cleanup."""
        errors = []
        for key in self.api.list("/account/keys", "ssh_keys"):
            if key.get("name") == name:
                try:
                    self.api.request("DELETE", f"/account/keys/{identity(key)}", missing_ok=True)
                except Exception as error:  # noqa: BLE001 - attempt every remaining resource
                    errors.append(str(error))
        if errors:
            raise RuntimeError("; ".join(errors))

    def cleanup(self):
        """Attempt every matching resource even if inventory or one deletion fails."""
        errors, ids = [], set(self.ids)
        try:
            ids.update(identity(item) for item in self.droplets() if item.get("name") == self.name)
        except Exception as error:  # noqa: BLE001 - known IDs remain usable after inventory failure
            errors.append(str(error))
        for resource_id in sorted(ids):
            try:
                self.destroy(resource_id)
            except Exception as error:  # noqa: BLE001 - attempt every remaining resource
                errors.append(str(error))
        try:
            self.delete_keys(self.name)
        except Exception as error:  # noqa: BLE001 - retain earlier cleanup failures
            errors.append(str(error))
        if errors:
            raise RuntimeError("; ".join(errors))

    def reap(self):
        """Delete tagged writers older than their four-hour recovery deadline."""
        errors = []
        for droplet in self.droplets():
            created = datetime.fromisoformat(droplet["created_at"])
            if (datetime.now(UTC) - created).total_seconds() > 14400:
                try:
                    self.destroy(identity(droplet))
                    self.delete_keys(droplet["name"])
                except Exception as error:  # noqa: BLE001 - attempt every remaining resource
                    errors.append(str(error))
        if errors:
            raise RuntimeError("; ".join(errors))

    def run(self):
        """Refuse overlapping writers and always attempt cleanup after provisioning."""
        self.reap()
        if self.droplets():
            raise RuntimeError("A previous updater Droplet still exists; refusing another writer.")
        directory = logs()
        with tempfile.TemporaryDirectory(
            dir=os.environ["RUNNER_TEMP"], prefix="updateloop-"
        ) as work:
            failed = False
            try:
                self.provision(Path(work), directory)
            except BaseException:
                failed = True
                raise
            finally:
                try:
                    self.cleanup()
                except Exception as error:
                    print(f"Cleanup failed: {error}", file=sys.stderr)
                    if not failed:
                        raise RuntimeError(f"Update succeeded; cleanup failed: {error}") from error

    def provision(self, work, directory):
        """Create one writer, verify SSH, and run both updater phases under systemd."""
        for name in ("client", "host"):
            command(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(work / name)])
        key = self.api.request(
            "POST",
            "/account/keys",
            {"name": self.name, "public_key": (work / "client.pub").read_text()},
        )
        cloud_init = {
            "ssh_keys": {
                "ed25519_private": (work / "host").read_text(),
                "ed25519_public": (work / "host.pub").read_text(),
            },
            "ssh_pwauth": False,
            "package_update": True,
            "packages": ["docker.io"],
            "runcmd": [["systemctl", "enable", "--now", "docker"]],
        }
        response = self.api.request(
            "POST",
            "/droplets",
            {
                "name": self.name,
                "image": "ubuntu-24-04-x64",
                "region": os.environ["DROPLET_REGION"],
                "size": os.environ["DROPLET_SIZE"],
                "ssh_keys": [identity(key.get("ssh_key"))],
                "tags": [self.tag],
                "user_data": "#cloud-config\n" + json.dumps(cloud_init),
            },
        )
        droplet = response.get("droplet")
        resource_id = identity(droplet)
        if droplet.get("name") != self.name:
            raise ValueError("Unexpected created Droplet name")
        self.ids = [resource_id]
        output("droplet_ids", self.ids)
        (directory / "droplet.json").write_text(
            json.dumps({key: droplet.get(key) for key in ("id", "name", "created_at")}),
            encoding="utf-8",
        )
        for attempt in range(60):
            droplet = self.api.request("GET", f"/droplets/{resource_id}")["droplet"]
            addresses = [
                item["ip_address"]
                for item in droplet.get("networks", {}).get("v4", [])
                if item.get("type") == "public"
            ]
            if droplet.get("status") == "active" and len(addresses) == 1:
                address = str(ipaddress.IPv4Address(addresses[0]))
                break
            time.sleep(5)
        else:
            raise RuntimeError("Expected exactly one active Droplet with a public IPv4 address")
        (work / "known_hosts").write_text(
            f"{address} {(work / 'host.pub').read_text().strip()}\n", encoding="utf-8"
        )
        ssh = [
            "ssh",
            "-i",
            str(work / "client"),
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={work / 'known_hosts'}",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=3",
            f"root@{address}",
        ]
        for attempt in range(60):
            try:
                command([*ssh, "true"], capture=True, quiet=True)
                break
            except subprocess.CalledProcessError:
                time.sleep(5)
        else:
            raise RuntimeError("SSH did not become ready")
        command(
            ["timeout", "15m", *ssh, "cloud-init status --wait"], log=directory / "bootstrap.log"
        )
        command([*ssh, "umask 077; cat > /root/.env.prod"], input=environment())
        image = shlex.quote(os.environ["UPDATELOOP_IMAGE"])
        actor = shlex.quote(os.environ["GITHUB_ACTOR"])
        command(
            [*ssh, f"docker login ghcr.io --username {actor} --password-stdin"],
            input=os.environ["GH_TOKEN"].encode(),
        )
        command([*ssh, f"docker pull {image}"], log=directory / "image.log")
        command(
            [*ssh, "docker logout ghcr.io; install -d -o 10001 -g 10001 /var/lib/arkwaifu-cache"]
        )
        command(
            [*ssh, "cat > /root/run_updateloop.py"],
            input=Path(__file__).with_name("run_updateloop.py").read_bytes(),
        )
        command(
            [
                *ssh,
                (
                    "systemd-run --unit=arkwaifu-updateloop --wait --pipe "
                    "-p RuntimeMaxSec=9000 -p 'ExecStopPost=-/usr/bin/docker rm -f arkwaifu-updateloop' "
                    "/usr/bin/docker run --rm --name arkwaifu-updateloop --entrypoint /app/.venv/bin/python "
                    "--env-file /root/.env.prod -e ARKWAIFU_EXTRACTION_WORKERS=4 -e ARKWAIFU_DOWNLOAD_WORKERS=16 "
                    "-v /var/lib/arkwaifu-cache:/app/.cache -v /root/run_updateloop.py:/run_updateloop.py:ro "
                    f"{image} /run_updateloop.py"
                ),
            ],
            log=directory / "updateloop.log",
        )


def main():
    """Report the failed phase without masking an update failure with cleanup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "run", "cleanup", "reap"))
    action = parser.parse_args().action
    try:
        if action == "check":
            check()
        else:
            coordinator = Coordinator(DigitalOcean(os.environ["DIGITALOCEAN_ACCESS_TOKEN"]))
            getattr(coordinator, action)()
        return 0
    except Exception as error:  # noqa: BLE001 - report the failed CLI phase
        message = f"{action} failed: {error}"
        print(message, file=sys.stderr)
        if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write(message + "\n")
        return 1


def interrupted(signum, _frame):
    """Unwind the resource owner's finally block when the runner terminates."""
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    sys.exit(main())

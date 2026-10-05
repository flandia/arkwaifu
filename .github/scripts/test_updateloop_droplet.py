"""Offline regression tests for the production writer and cleanup commands."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import run_updateloop
import updateloop_droplet as workflow


def http_error(status, message="failed"):
    return HTTPError(
        workflow.API + "/droplets",
        status,
        message,
        {},
        io.BytesIO(json.dumps({"message": message}).encode()),
    )


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.api = workflow.DigitalOcean("private-token")
        self.open = patch.object(self.api.opener, "open").start()
        self.addCleanup(patch.stopall)
        self.sleep = patch.object(workflow.time, "sleep").start()

    def respond(self, payload):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(payload).encode()
        return response

    def test_post_preserves_provider_error_without_retrying(self):
        self.open.side_effect = http_error(422, "Size is not available in this region.")
        with self.assertRaisesRegex(workflow.ApiError, "HTTP 422.*Size is not available"):
            self.api.request("POST", "/droplets", {"user_data": "private host key"})
        self.assertEqual(self.open.call_count, 1)
        self.sleep.assert_not_called()
        request = self.open.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer private-token")
        self.assertEqual(json.loads(request.data), {"user_data": "private host key"})

    def test_error_diagnostics_redact_the_provider_token(self):
        self.open.side_effect = http_error(401, "invalid private-token")
        with self.assertRaisesRegex(workflow.ApiError, r"HTTP 401: invalid \*\*\*"):
            self.api.request("GET", "/droplets")

    def test_ambiguous_create_is_not_retried(self):
        self.open.side_effect = URLError("connection lost")
        with self.assertRaises(URLError):
            self.api.request("POST", "/droplets", {})
        self.assertEqual(self.open.call_count, 1)

    def test_read_retries_transient_errors_then_succeeds(self):
        self.open.side_effect = [http_error(503), URLError("timeout"), self.respond({})]
        self.assertEqual(self.api.request("GET", "/droplets"), {})
        self.assertEqual(self.open.call_count, 3)
        self.assertEqual(self.sleep.call_count, 2)

    def test_read_exhaustion_and_authentication_failure_remain_errors(self):
        for status, attempts in [(503, 3), (403, 1)]:
            with self.subTest(status=status):
                self.open.reset_mock()
                self.open.side_effect = [http_error(status) for _ in range(attempts)]
                with self.assertRaises(workflow.ApiError):
                    self.api.request("GET", "/droplets")
                self.assertEqual(self.open.call_count, attempts)

    def test_missing_key_is_success_but_permission_errors_are_not(self):
        self.open.side_effect = http_error(404)
        self.assertIsNone(self.api.request("DELETE", "/account/keys/10", missing_ok=True))
        self.open.side_effect = http_error(403)
        with self.assertRaises(workflow.ApiError):
            self.api.request("DELETE", "/account/keys/10", missing_ok=True)

    def test_inventory_follows_pages_and_rejects_foreign_links(self):
        next_page = workflow.API + "/droplets?page=2"
        self.open.side_effect = [
            self.respond({"droplets": [{"id": 1}], "links": {"pages": {"next": next_page}}}),
            self.respond({"droplets": [{"id": 2}]}),
        ]
        self.assertEqual(self.api.list("/droplets", "droplets"), [{"id": 1}, {"id": 2}])
        self.open.side_effect = [
            self.respond(
                {"droplets": [], "links": {"pages": {"next": "https://elsewhere.test/droplets"}}}
            )
        ]
        with self.assertRaisesRegex(ValueError, "pagination"):
            self.api.list("/droplets", "droplets")
        self.open.side_effect = [self.respond({"droplets": {"id": 1}})]
        with self.assertRaisesRegex(ValueError, "inventory"):
            self.api.list("/droplets", "droplets")


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = {
            "RUNNER_TEMP": str(self.root),
            "GITHUB_OUTPUT": str(self.root / "output"),
            "DIGITALOCEAN_ACCESS_TOKEN": "do-token",
            "DROPLET_NAME": "arkwaifu-123-1",
            "DROPLET_TAG": "test-updateloop",
            "DROPLET_REGION": "sgp1",
            "DROPLET_SIZE": "s-8vcpu-16gb",
            "UPDATELOOP_IMAGE": "ghcr.io/test/updater:latest",
            "UPDATELOOP_ENV": "ARKWAIFU_S3_BUCKET=production\nARKWAIFU_GITHUB_TOKEN=old-token",
            "GH_TOKEN": "workflow-token",
            "GITHUB_ACTOR": "test",
        }
        patch.dict(os.environ, self.environment, clear=True).start()
        patch.object(workflow.time, "sleep").start()
        self.addCleanup(patch.stopall)
        self.api = Mock()
        self.coordinator = workflow.Coordinator(self.api)
        self.api.list.return_value = []

    def droplet(self, identity=1, name="arkwaifu-123-1", age=0):
        return {
            "id": identity,
            "name": name,
            "created_at": (datetime.now(UTC) - timedelta(hours=age)).isoformat(),
        }

    def test_cleanup_only_targets_this_run_and_checks_known_ids(self):
        self.coordinator.ids = [3]
        self.api.list.side_effect = [
            [self.droplet(), self.droplet(2, "other-run")],
            [{"id": 10, "name": "arkwaifu-123-1"}, {"id": 20, "name": "other-run"}],
        ]
        self.api.request.return_value = None
        self.coordinator.cleanup()
        targets = [call.args[1] for call in self.api.request.call_args_list]
        self.assertEqual(targets, ["/droplets/1", "/droplets/3", "/account/keys/10"])

    def test_cleanup_continues_after_one_failure(self):
        self.api.list.side_effect = [
            [self.droplet(), self.droplet(2)],
            [{"id": 10, "name": "arkwaifu-123-1"}],
        ]
        with (
            patch.object(
                self.coordinator, "destroy", side_effect=[RuntimeError("stuck"), None]
            ) as destroy,
            self.assertRaisesRegex(RuntimeError, "stuck"),
        ):
            self.coordinator.cleanup()
        self.assertEqual(destroy.call_count, 2)
        self.api.request.assert_called_once_with("DELETE", "/account/keys/10", missing_ok=True)

    def test_inventory_failure_still_checks_known_ids(self):
        self.coordinator.ids = [1]
        self.api.list.side_effect = [RuntimeError("inventory unavailable"), []]
        self.api.request.return_value = None
        with self.assertRaisesRegex(RuntimeError, "inventory unavailable"):
            self.coordinator.cleanup()
        self.api.request.assert_called_once_with("GET", "/droplets/1", missing_ok=True, attempts=1)

    def test_deletion_must_be_confirmed_and_transient_errors_can_recover(self):
        self.api.request.side_effect = [workflow.ApiError(503, "temporary"), {}, {}, None]
        self.coordinator.destroy(1)
        methods = [call.args[0] for call in self.api.request.call_args_list]
        self.assertEqual(methods, ["GET", "GET", "DELETE", "GET"])
        self.api.request.side_effect = None
        self.api.request.return_value = {}
        with self.assertRaisesRegex(RuntimeError, "confirm deletion"):
            self.coordinator.destroy(1)

    def test_reap_leaves_young_writers_and_removes_expired_ones(self):
        self.api.list.return_value = [self.droplet(age=5), self.droplet(2, "young", age=1)]
        with (
            patch.object(self.coordinator, "destroy") as destroy,
            patch.object(self.coordinator, "delete_keys") as keys,
        ):
            self.coordinator.reap()
        destroy.assert_called_once_with(1)
        keys.assert_called_once_with("arkwaifu-123-1")
        self.api.list.return_value = [{"id": 1, "created_at": "invalid"}]
        with self.assertRaises(ValueError):
            self.coordinator.reap()

    def test_live_writer_prevents_provisioning(self):
        self.api.list.return_value = [self.droplet()]
        with (
            patch.object(workflow, "command") as command,
            self.assertRaisesRegex(RuntimeError, "refusing another writer"),
        ):
            self.coordinator.run()
        command.assert_not_called()
        self.api.request.assert_not_called()

    def test_cleanup_failure_preserves_the_update_outcome(self):
        for update_error in [None, workflow.ApiError(422, "unsupported size"), SystemExit(143)]:
            with (
                self.subTest(update_error=update_error),
                patch.object(self.coordinator, "provision", side_effect=update_error),
                patch.object(
                    self.coordinator, "cleanup", side_effect=RuntimeError("cleanup unavailable")
                ) as cleanup,
                redirect_stderr(io.StringIO()),
            ):
                expected = type(update_error) if update_error else RuntimeError
                with self.assertRaises(expected) as caught:
                    self.coordinator.run()
                if update_error is None:
                    self.assertIn("Update succeeded; cleanup failed", str(caught.exception))
                else:
                    self.assertIs(caught.exception, update_error)
                cleanup.assert_called_once()

    def generate_keys(self, args, **kwargs):
        if args[0] == "ssh-keygen":
            path = Path(args[-1])
            path.write_text("private host key")
            path.with_suffix(".pub").write_text("ssh-ed25519 public-key")
        return b""

    def test_create_error_and_malformed_success_still_cleanup(self):
        for result in [
            workflow.ApiError(422, "unsupported size"),
            {"droplet": {"id": True}},
            {"droplet": {"id": 1, "name": "other-run"}},
        ]:
            with (
                self.subTest(result=result),
                patch.object(workflow, "command", side_effect=self.generate_keys),
                patch.object(self.coordinator, "cleanup") as cleanup,
            ):
                self.api.request.side_effect = [{"ssh_key": {"id": 10}}, result]
                with self.assertRaises((workflow.ApiError, ValueError)):
                    self.coordinator.run()
                cleanup.assert_called_once()

    def test_successful_run_preserves_remote_safeguards_and_credentials(self):
        self.api.request.side_effect = [
            {"ssh_key": {"id": 10}},
            {"droplet": {"id": 1, "name": "arkwaifu-123-1", "created_at": "now"}},
            {
                "droplet": {
                    "status": "active",
                    "networks": {"v4": [{"type": "public", "ip_address": "192.0.2.1"}]},
                }
            },
        ]
        with (
            patch.object(workflow, "command", side_effect=self.generate_keys) as command,
            patch.object(self.coordinator, "cleanup") as cleanup,
        ):
            self.coordinator.run()
        creation = self.api.request.call_args_list[1].args[2]
        self.assertNotIn("workflow-token", creation["user_data"])
        self.assertIn("private host key", creation["user_data"])
        calls = command.call_args_list
        remote_commands = "\n".join(" ".join(call.args[0]) for call in calls)
        self.assertIn("StrictHostKeyChecking=yes", remote_commands)
        self.assertIn("RuntimeMaxSec=9000", remote_commands)
        self.assertIn("ExecStopPost=", remote_commands)
        self.assertIn("/app/.cache", remote_commands)
        self.assertIn("ARKWAIFU_EXTRACTION_WORKERS=4", remote_commands)
        self.assertIn("run_updateloop.py", remote_commands)
        credentials = next(
            call.kwargs["input"] for call in calls if "cat > /root/.env.prod" in call.args[0][-1]
        )
        self.assertIn(b"ARKWAIFU_GITHUB_TOKEN=workflow-token", credentials)
        self.assertNotIn(b"old-token", credentials)
        self.assertEqual(self.coordinator.ids, [1])
        self.assertIn("droplet_ids=[1]", (self.root / "output").read_text())
        cleanup.assert_called_once()

    def test_preflight_requires_valid_success_and_forwards_token(self):
        for payload, failure in [
            (b'{"update_needed":false}', False),
            (b'{"update_needed":true}', False),
            (b"{}", True),
        ]:
            with self.subTest(payload=payload):
                (self.root / "output").write_text("")

                def execute(args, payload=payload, **kwargs):
                    if args[:2] == ["docker", "run"]:
                        env_file = Path(args[args.index("--env-file") + 1]).read_text()
                        self.assertIn("ARKWAIFU_GITHUB_TOKEN=workflow-token", env_file)
                        return payload
                    return b""

                with patch.object(workflow, "command", side_effect=execute):
                    if failure:
                        with self.assertRaises(ValueError):
                            workflow.check()
                        self.assertEqual((self.root / "output").read_text(), "")
                    else:
                        workflow.check()
                        self.assertIn("update_needed=", (self.root / "output").read_text())

    def test_failed_preflight_never_emits_a_decision(self):
        decision = b'{"update_needed":false}'

        def execute(args, **kwargs):
            if args[:2] == ["docker", "run"]:
                raise subprocess.CalledProcessError(1, args, output=decision)
            return b""

        with (
            patch.object(workflow, "command", side_effect=execute),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            workflow.check()
        self.assertFalse((self.root / "output").exists())
        self.assertEqual((self.root / "updateloop-logs/preflight.json").read_bytes(), decision)

    def test_subprocess_logs_preserve_output_and_failure(self):
        log = self.root / "command.log"
        with (
            redirect_stdout(io.StringIO()) as output,
            self.assertRaises(subprocess.CalledProcessError),
        ):
            workflow.command(
                [sys.executable, "-c", "print('phase output'); raise SystemExit(2)"], log=log
            )
        self.assertIn("phase output", output.getvalue())
        self.assertIn(b"phase output", log.read_bytes())

    def test_both_remote_phases_are_attempted_and_failures_are_preserved(self):
        for codes in [(0, 0), (1, 0), (0, 1), (1, 1)]:
            with (
                self.subTest(codes=codes),
                patch.object(
                    run_updateloop.subprocess,
                    "run",
                    side_effect=[Mock(returncode=code) for code in codes],
                ) as run,
            ):
                self.assertEqual(run_updateloop.main(), int(any(codes)))
                self.assertEqual(
                    [call.args[0][1:] for call in run.call_args_list],
                    [["run"], ["run", "--archive"]],
                )


if __name__ == "__main__":
    unittest.main()

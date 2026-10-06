"""Exercise the delete command without sending requests to real notes."""

import json
from unittest.mock import Mock

import httpx
import pytest
from typer.testing import CliRunner

from getnotes_cli import cli
from getnotes_cli.auth import AuthToken
from getnotes_cli.config import OPENAPI_NOTE_DELETE_URL


runner = CliRunner()


@pytest.fixture
def delete_api(monkeypatch):
    auth = AuthToken(api_key="gk_live_test", client_id="cli_test")
    get_auth = Mock(return_value=auth)
    monkeypatch.setattr(cli, "_get_auth", get_auth)
    requests = []
    response = {"success": True, "data": {}}

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=response)

    # Run through the real OpenAPI client, including payload and error handling.
    client = httpx.Client(transport=httpx.MockTransport(handle))
    monkeypatch.setattr("getnotes_cli.openapi_client.httpx.Client", lambda **kwargs: client)
    yield get_auth, requests, response, client
    client.close()


@pytest.mark.parametrize("args,answer", [
    (["note-123"], "y\n"),
    (["note-123", "--confirm"], None),
    (["note-123", "-y"], None),
])
def test_delete_confirmed_note(delete_api, args, answer):
    get_auth, requests, _, client = delete_api

    result = runner.invoke(cli.app, ["delete", *args], input=answer)

    assert result.exit_code == 0, result.output
    assert "云端笔记已删除" in result.output
    assert "note-123" in result.output
    get_auth.assert_called_once_with(None)
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == OPENAPI_NOTE_DELETE_URL
    assert json.loads(request.content) == {"note_id": "note-123"}
    assert request.headers["Authorization"] == "gk_live_test"
    assert request.headers["X-Client-ID"] == "cli_test"
    assert client.is_closed


@pytest.mark.parametrize("answer", ["n\n", ""])
def test_delete_cancelled_or_no_input_does_not_send_request(delete_api, answer):
    get_auth, requests, _, _ = delete_api

    result = runner.invoke(cli.app, ["delete", "note-123"], input=answer)

    assert result.exit_code != 0
    assert "云端笔记已删除" not in result.output
    get_auth.assert_not_called()
    assert requests == []


@pytest.mark.parametrize("args", [[], ["   ", "-y"]])
def test_delete_requires_nonempty_id(delete_api, args):
    get_auth, requests, _, _ = delete_api

    result = runner.invoke(cli.app, ["delete", *args])

    assert result.exit_code == 2
    get_auth.assert_not_called()
    assert requests == []


@pytest.mark.parametrize("flag", ["--api-key", "--token", "-t"])
def test_delete_passes_api_key_to_auth_resolver(delete_api, flag):
    get_auth, requests, _, _ = delete_api

    result = runner.invoke(cli.app, ["delete", " note-123 ", "-y", flag, "gk_override"])

    assert result.exit_code == 0, result.output
    get_auth.assert_called_once_with("gk_override")
    assert json.loads(requests[0].content) == {"note_id": "note-123"}


def test_delete_reports_api_failure(delete_api):
    _, requests, response, client = delete_api
    response.update(success=False, error="note not found")

    result = runner.invoke(cli.app, ["delete", "note-123", "-y"])

    assert result.exit_code == 1
    assert "删除失败" in result.output
    assert "note not found" in result.output
    assert "云端笔记已删除" not in result.output
    assert len(requests) == 1
    assert client.is_closed

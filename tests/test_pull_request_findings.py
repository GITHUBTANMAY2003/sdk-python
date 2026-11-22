from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest

from proofline import ProoflineError, PullRequestFindings

from .fixtures import ORG, TOKEN, assessment, code_assessment, finding, review, summary
from .http_server import Reply, Request, Server
from .test_http import MODES, call, session

RUNS = f"/api/v1/organizations/{ORG}/reviews/pr/name/42"


def finding_id(number: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-1000000000{number:02d}")


def finding_at(number: int, **overrides: Any) -> dict[str, Any]:
    return {**finding(), "id": str(finding_id(number)), **overrides}


def runs(*numbers: int, cursor: str | None = None) -> dict[str, Any]:
    return {
        "items": [{**summary(), "run_number": number} for number in numbers],
        "filters": {"repositories": [], "environments": [], "authors": []},
        "truncated": cursor is not None,
        "next_cursor": cursor,
    }


def run(number: int, status: str = "COMPLETED") -> dict[str, Any]:
    return {**review(status), "run_number": number}


def merged_run(number: int) -> dict[str, Any]:
    # A withheld review with a resolved finding: nothing may be dropped.
    body = run(number)
    body["publication"] = "WITHHELD"
    body["code_assessment"] = {
        **code_assessment(),
        "findings": [finding_at(1), finding_at(2, lifecycle_state="RESOLVED")],
    }
    body["assessments"] = [
        {**assessment(), "findings": [finding_at(3)]},
        {**assessment(), "findings": [finding_at(4), finding_at(5)]},
    ]
    return body


def serve(pages: list[dict[str, Any]], detail: dict[str, Any]) -> Any:
    def respond(request: Request, index: int) -> Reply:
        assert request.method == "GET"
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        path = urlsplit(request.path).path
        if path == RUNS:
            return Reply(body=pages[index])
        assert path == f"{RUNS}/runs/{detail['run_number']}"
        return Reply(body=detail)

    return respond


def paths(server: Server) -> list[str]:
    return [urlsplit(request.path).path for request in server.requests]


def queries(server: Server) -> list[dict[str, list[str]]]:
    return [parse_qs(urlsplit(request.path).query) for request in server.requests]


async def findings_of(mode: str, respond: Any, **kwargs: Any) -> tuple[Any, Server]:
    with Server(respond) as server:
        async with session(mode, server.url) as client:
            result = await call(client, "get_pull_request_findings", ORG, "name", 42, **kwargs)
    return result, server


@MODES
async def test_latest_run_is_the_highest_run_number(mode: str) -> None:
    # The listing order is not trusted: the highest run number wins.
    result, server = await findings_of(mode, serve([runs(2, 5, 3)], run(5)))

    assert isinstance(result, PullRequestFindings)
    assert result.run_number == 5
    assert result.review.run_number == 5
    assert paths(server) == [RUNS, f"{RUNS}/runs/5"]
    assert queries(server)[0]["limit"] == ["100"]
    assert "cursor" not in queries(server)[0]


@MODES
async def test_explicit_run_number_makes_one_request(mode: str) -> None:
    result, server = await findings_of(mode, serve([], run(2)), run_number=2)

    assert isinstance(result, PullRequestFindings)
    assert result.run_number == 2
    assert paths(server) == [f"{RUNS}/runs/2"]


@MODES
@pytest.mark.parametrize("bad", [0, -1, True, "2", 1.0])
async def test_invalid_run_number_is_refused_before_any_request(mode: str, bad: Any) -> None:
    with pytest.raises(ValueError):
        await findings_of(mode, serve([], run(1)), run_number=bad)


@MODES
async def test_code_findings_come_first_then_each_environment_in_order(mode: str) -> None:
    result, _ = await findings_of(mode, serve([runs(1)], merged_run(1)))

    assert isinstance(result, PullRequestFindings)
    assert [item.id for item in result.findings] == [finding_id(n) for n in range(1, 6)]
    assert result.findings[1].lifecycle_state == "RESOLVED"
    assert result.review.publication == "WITHHELD"
    assert isinstance(result.findings, tuple)


@MODES
async def test_running_review_is_returned_with_its_status(mode: str) -> None:
    body = run(4, "RUNNING")
    body["code_assessment"] = {**code_assessment("RUNNING"), "findings": [finding_at(1)]}
    body["assessments"] = [assessment("RUNNING")]

    result, _ = await findings_of(mode, serve([runs(4)], body))

    assert isinstance(result, PullRequestFindings)
    assert result.status == "RUNNING"
    assert [item.id for item in result.findings] == [finding_id(1)]


@MODES
async def test_pull_request_without_runs_returns_none(mode: str) -> None:
    result, server = await findings_of(mode, serve([runs()], run(1)))

    assert result is None
    assert paths(server) == [RUNS]


@MODES
async def test_newest_run_on_a_second_page_is_found(mode: str) -> None:
    pages = [runs(3, 2, cursor="opaque+/cursor"), runs(7, 1)]

    result, server = await findings_of(mode, serve(pages, run(7)))

    assert isinstance(result, PullRequestFindings)
    assert result.run_number == 7
    assert paths(server) == [RUNS, RUNS, f"{RUNS}/runs/7"]
    assert queries(server)[1]["cursor"] == ["opaque+/cursor"]


async def test_async_client_matches_sync_client() -> None:
    def facts(result: PullRequestFindings) -> tuple[Any, ...]:
        return (
            result.run_number,
            result.status,
            result.review.id,
            [item.to_dict() for item in result.findings],
        )

    pages = [runs(1, cursor="next"), runs(6)]
    sync, _ = await findings_of("sync", serve(pages, merged_run(6)))
    async_, _ = await findings_of("async", serve(pages, merged_run(6)))

    assert isinstance(sync, PullRequestFindings)
    assert isinstance(async_, PullRequestFindings)
    assert facts(sync) == facts(async_)
    assert type(sync) is type(async_)


@MODES
async def test_listed_runs_without_run_numbers_are_an_invalid_response(mode: str) -> None:
    unnumbered = runs()
    unnumbered["items"] = [summary()]

    with pytest.raises(ProoflineError) as raised:
        await findings_of(mode, serve([unnumbered], run(1)))
    assert raised.value.type == "urn:proofline:sdk:invalid-response"


@MODES
async def test_detail_for_another_run_is_an_invalid_response(mode: str) -> None:
    def respond(request: Request, index: int) -> Reply:
        return Reply(body=run(9))

    with pytest.raises(ProoflineError) as raised:
        await findings_of(mode, respond, run_number=2)
    assert raised.value.type == "urn:proofline:sdk:invalid-response"


@MODES
async def test_run_pages_beyond_the_bound_raise_instead_of_guessing(mode: str) -> None:
    def respond(request: Request, index: int) -> Reply:
        return Reply(body=runs(index + 1, cursor=f"page-{index}"))

    with pytest.raises(ProoflineError) as raised:
        await findings_of(mode, respond)
    assert raised.value.type == "urn:proofline:sdk:pagination-limit"

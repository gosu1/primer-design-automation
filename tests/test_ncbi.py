import os

import pytest
import requests

from app.ncbi import FETCH_BATCH, NcbiClient, NcbiError


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        return self._json


class FakeSession:
    """준비된 응답을 순서대로 돌려주고, 받은 요청을 기록한다. 예외 객체가 들어 있으면 던진다."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        return self._next(url, params)

    def post(self, url, data=None, timeout=None):
        return self._next(url, data)

    def _next(self, url, params):
        self.calls.append((url, params))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_client(responses, email="", api_key=""):
    client = NcbiClient(email=email, api_key=api_key)
    client.session = FakeSession(responses)
    client.sleeps = []
    client._sleep = client.sleeps.append
    return client


SEARCH_JSON = {"esearchresult": {"count": "25497", "idlist": ["1", "2", "3"]}}


def test_search_parses_count_and_ids():
    client = make_client([FakeResponse(json_data=SEARCH_JSON)])
    assert client.search("sars-cov-2 whole genome", 0, 3) == (25497, ["1", "2", "3"])
    url, params = client.session.calls[0]
    assert url == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    assert params["db"] == "nucleotide"
    assert params["term"] == "sars-cov-2 whole genome"
    assert params["retstart"] == 0 and params["retmax"] == 3 and params["retmode"] == "json"


def test_every_request_carries_tool_email_and_key():
    client = make_client([FakeResponse(json_data=SEARCH_JSON)], email="a@b.c", api_key="KEY")
    client.search("x", 0, 1)
    params = client.session.calls[0][1]
    assert params["tool"] == "primer-design-automation"
    assert params["email"] == "a@b.c"
    assert params["api_key"] == "KEY"


def test_email_and_key_omitted_when_empty():
    client = make_client([FakeResponse(json_data=SEARCH_JSON)])
    client.search("x", 0, 1)
    params = client.session.calls[0][1]
    assert "email" not in params and "api_key" not in params


def test_search_error_field_raises():
    client = make_client([FakeResponse(json_data={"esearchresult": {"ERROR": "Empty term"}})])
    with pytest.raises(NcbiError, match="Empty term"):
        client.search("", 0, 1)


def test_summaries_parses_fields():
    data = {"result": {
        "uids": ["10", "11"],
        "10": {"uid": "10", "accessionversion": "LR881868.1", "title": "A", "slen": 29903},
        "11": {"uid": "11", "accessionversion": "MW1.1", "title": "B", "slen": 100},
    }}
    client = make_client([FakeResponse(json_data=data)])
    assert client.summaries(["10", "11"]) == [
        {"uid": "10", "accession": "LR881868.1", "title": "A", "length": 29903},
        {"uid": "11", "accession": "MW1.1", "title": "B", "length": 100},
    ]
    url, params = client.session.calls[0]
    assert url.endswith("esummary.fcgi")
    assert params["id"] == "10,11" and params["retmode"] == "json"


def test_summaries_empty_list_makes_no_request():
    client = make_client([])
    assert client.summaries([]) == []
    assert client.session.calls == []


def test_fetch_fasta_returns_text():
    client = make_client([FakeResponse(text=">A\nACGT\n")])
    assert client.fetch_fasta(["1", "2"]) == ">A\nACGT\n"
    url, params = client.session.calls[0]
    assert url.endswith("efetch.fcgi")
    assert params["id"] == "1,2"
    assert params["rettype"] == "fasta" and params["retmode"] == "text"


def test_fetch_fasta_rejects_more_than_batch():
    client = make_client([])
    with pytest.raises(ValueError):
        client.fetch_fasta(["1"] * (FETCH_BATCH + 1))


def test_retries_then_succeeds():
    client = make_client([
        FakeResponse(status_code=429),
        FakeResponse(status_code=503),
        requests.ConnectionError(),
        FakeResponse(json_data=SEARCH_JSON),
    ])
    assert client.search("x", 0, 3)[0] == 25497
    assert len(client.session.calls) == 4
    assert [s for s in client.sleeps if s >= 2] == [2, 4, 8]


def test_gives_up_after_three_retries():
    client = make_client([FakeResponse(status_code=503)] * 4)
    with pytest.raises(NcbiError, match="응답이 없습니다"):
        client.search("x", 0, 3)
    assert len(client.session.calls) == 4


def test_client_error_raises_immediately():
    client = make_client([FakeResponse(status_code=400)])
    with pytest.raises(NcbiError, match="400"):
        client.search("x", 0, 3)
    assert len(client.session.calls) == 1


def test_throttle_keeps_requests_a_third_of_a_second_apart():
    client = make_client([FakeResponse(json_data=SEARCH_JSON)] * 3)
    for _ in range(3):
        client.search("x", 0, 3)
    waits = [s for s in client.sleeps if s < 2]
    assert len(waits) == 2
    assert all(0.3 < w <= 1 / 3 for w in waits)


def test_throttle_is_a_tenth_of_a_second_with_api_key():
    client = make_client([FakeResponse(json_data=SEARCH_JSON)] * 2, api_key="KEY")
    client.search("x", 0, 3)
    client.search("x", 0, 3)
    assert len(client.sleeps) == 1
    assert 0.09 < client.sleeps[0] <= 0.1


@pytest.mark.skipif(not os.environ.get("NCBI_LIVE"), reason="NCBI_LIVE=1 일 때만 실제 접속")
def test_live_search_and_fetch():
    client = NcbiClient()
    count, ids = client.search("LR881868.1", 0, 1)
    assert count >= 1
    assert client.fetch_fasta(ids[:1]).startswith(">LR881868.1")

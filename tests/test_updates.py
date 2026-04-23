import responses

from container_tracker.core.updates import UpdateInfo, check_for_update


GITHUB_RELEASES_URL = "https://api.github.com/repos/m-mcohen/container-tracker/releases/latest"


class TestCheckForUpdate:
    @responses.activate
    def test_newer_release_returns_update_info(self) -> None:
        responses.add(
            responses.GET,
            GITHUB_RELEASES_URL,
            json={"tag_name": "v1.2.0", "html_url": "https://github.com/m-mcohen/container-tracker/releases/v1.2.0"},
            status=200,
        )
        result = check_for_update("1.1.0")
        assert result == UpdateInfo(
            version="1.2.0",
            html_url="https://github.com/m-mcohen/container-tracker/releases/v1.2.0",
        )

    @responses.activate
    def test_same_version_returns_none(self) -> None:
        responses.add(
            responses.GET,
            GITHUB_RELEASES_URL,
            json={"tag_name": "v1.1.0", "html_url": "https://..."},
            status=200,
        )
        assert check_for_update("1.1.0") is None

    @responses.activate
    def test_older_release_returns_none(self) -> None:
        responses.add(
            responses.GET,
            GITHUB_RELEASES_URL,
            json={"tag_name": "v1.0.0", "html_url": "https://..."},
            status=200,
        )
        assert check_for_update("1.1.0") is None

    @responses.activate
    def test_handles_tag_without_v_prefix(self) -> None:
        responses.add(
            responses.GET,
            GITHUB_RELEASES_URL,
            json={"tag_name": "1.2.0", "html_url": "https://..."},
            status=200,
        )
        assert check_for_update("1.1.0") is not None

    @responses.activate
    def test_404_returns_none(self) -> None:
        responses.add(responses.GET, GITHUB_RELEASES_URL, status=404)
        assert check_for_update("1.1.0") is None

    @responses.activate
    def test_403_rate_limit_returns_none(self) -> None:
        responses.add(responses.GET, GITHUB_RELEASES_URL, json={"message": "rate limit"}, status=403)
        assert check_for_update("1.1.0") is None

    @responses.activate
    def test_malformed_json_returns_none(self) -> None:
        responses.add(responses.GET, GITHUB_RELEASES_URL, body="not json", status=200)
        assert check_for_update("1.1.0") is None

    @responses.activate
    def test_missing_tag_returns_none(self) -> None:
        responses.add(responses.GET, GITHUB_RELEASES_URL, json={"html_url": "https://..."}, status=200)
        assert check_for_update("1.1.0") is None

    def test_offline_returns_none(self) -> None:
        # No responses.activate → requests will raise ConnectionError on any real call.
        # Check that the function swallows it.
        assert check_for_update("1.1.0") is None

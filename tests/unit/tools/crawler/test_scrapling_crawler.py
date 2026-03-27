"""Unit tests for Scrapling crawler backend."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.crawler.backend import CrawlOutput
from src.tools.crawler.scrapling_crawler import (
    ScraplingCrawler,
    _extract_title,
    _needs_browser,
    _needs_stealth,
    _html_to_markdown,
)


class TestNeedsBrowser:
    """Tests for Tier 1 -> Tier 2 escalation detection."""

    def test_4xx_status(self):
        assert _needs_browser("<html>Access Denied</html>", 403) is True
        assert _needs_browser("<html>Not Found</html>", 404) is True

    def test_5xx_status(self):
        assert _needs_browser("<html>Server Error</html>", 500) is True

    def test_empty_body(self):
        assert _needs_browser("", 200) is True
        assert _needs_browser("   ", 200) is True

    def test_short_body(self):
        assert _needs_browser("<html><body>tiny</body></html>", 200) is True

    def test_cloudflare_signal(self):
        html = "<html><body>Just a moment... Checking your browser</body></html>" + "x" * 200
        assert _needs_browser(html, 200) is True

    def test_enable_javascript_signal(self):
        html = "<html><body>Please enable JavaScript to continue" + "x" * 200 + "</body></html>"
        assert _needs_browser(html, 200) is True

    def test_normal_page(self):
        html = "<html><body>" + "<p>Real content here.</p>" * 20 + "</body></html>"
        assert _needs_browser(html, 200) is False

    def test_case_insensitive(self):
        html = "<html><body>ACCESS DENIED" + "x" * 200 + "</body></html>"
        assert _needs_browser(html, 200) is True


class TestNeedsStealth:
    """Tests for Tier 2 -> Tier 3 escalation detection."""

    def test_403_status(self):
        assert _needs_stealth("<html>Blocked</html>", 403) is True

    def test_cloudflare_with_ray_id(self):
        html = "<html>Cloudflare challenge Ray ID: abc123</html>"
        assert _needs_stealth(html, 200) is True

    def test_cloudflare_just_a_moment(self):
        html = "<html>Cloudflare Just a moment...</html>"
        assert _needs_stealth(html, 200) is True

    def test_normal_page(self):
        html = "<html><body>Normal page content</body></html>"
        assert _needs_stealth(html, 200) is False

    def test_cloudflare_without_ray_id(self):
        # Cloudflare mention without ray id or just a moment is not stealth-needed
        html = "<html>Powered by Cloudflare</html>"
        assert _needs_stealth(html, 200) is False

    def test_401_status(self):
        assert _needs_stealth("<html>Unauthorized</html>", 401) is True

    def test_datadome_challenge(self):
        # DataDome anti-bot: short page with "enable JS" message
        html = '<html><body><p>Please enable JS and disable any ad blocker</p></body></html>'
        assert _needs_stealth(html, 200) is True

    def test_enable_js_on_large_page_not_stealth(self):
        # A large page that discusses "enable javascript" is not a challenge
        html = "<html><body>" + "x" * 3000 + "enable javascript" + "</body></html>"
        assert _needs_stealth(html, 200) is False


class TestHtmlToMarkdown:
    """Tests for HTML to markdown conversion."""

    def test_basic_conversion(self):
        html = "<h1>Title</h1><p>Paragraph text.</p>"
        md = _html_to_markdown(html)
        assert "Title" in md
        assert "Paragraph text." in md

    def test_links_preserved(self):
        html = '<a href="https://example.com">Link</a>'
        md = _html_to_markdown(html)
        assert "https://example.com" in md
        assert "Link" in md

    def test_empty_html(self):
        md = _html_to_markdown("")
        assert md.strip() == ""


class TestCrawlOutput:
    """Tests for CrawlOutput dataclass."""

    def test_create(self):
        output = CrawlOutput(title="Test", html="<p>Hi</p>", markdown="Hi")
        assert output.title == "Test"
        assert output.html == "<p>Hi</p>"
        assert output.markdown == "Hi"


# ---------------------------------------------------------------------------
# Helpers for tier dispatch tests
# ---------------------------------------------------------------------------

def _make_page_mock(title_text: str = "Test Page"):
    """Create a mock Scrapling page object with .css() for title extraction."""
    title_node = MagicMock()
    title_node.get.return_value = title_text

    page = MagicMock()
    page.css.return_value = title_node
    return page


_GOOD_HTML = "<html><head><title>Test Page</title></head><body>" + "<p>Content</p>" * 20 + "</body></html>"
_BLOCKED_HTML = "<html><body>Just a moment... Checking your browser Cloudflare Ray ID: abc</body></html>"
_STEALTH_HTML = "<html><body>Cloudflare challenge Ray ID: xyz Just a moment</body></html>"


class TestCrawlWithMetadataTiers:
    """Tests for the three-tier fallback dispatch in crawl_with_metadata()."""

    @pytest.mark.asyncio
    async def test_tier1_succeeds(self):
        """Tier 1 returns good content -> returns immediately, Tier 2/3 never called."""
        crawler = ScraplingCrawler()
        page = _make_page_mock("Tier1 Title")

        with (
            patch.object(crawler, "_tier1_fetch", new_callable=AsyncMock, return_value=(page, _GOOD_HTML, 200)) as t1,
            patch.object(crawler, "_tier2_fetch", new_callable=AsyncMock) as t2,
            patch.object(crawler, "_tier3_fetch", new_callable=AsyncMock) as t3,
        ):
            result = await crawler.crawl_with_metadata("https://example.com")

        t1.assert_awaited_once()
        t2.assert_not_awaited()
        t3.assert_not_awaited()
        assert result.title == "Tier1 Title"
        assert result.html == _GOOD_HTML
        assert "Content" in result.markdown

    @pytest.mark.asyncio
    async def test_tier1_insufficient_escalates_to_tier2(self):
        """Tier 1 returns blocked content -> escalates to Tier 2 which succeeds."""
        crawler = ScraplingCrawler()
        page_t1 = _make_page_mock()
        page_t2 = _make_page_mock("Tier2 Title")

        with (
            patch.object(crawler, "_tier1_fetch", new_callable=AsyncMock, return_value=(page_t1, _BLOCKED_HTML, 200)),
            patch.object(crawler, "_tier2_fetch", new_callable=AsyncMock, return_value=(page_t2, _GOOD_HTML, 200)) as t2,
            patch.object(crawler, "_tier3_fetch", new_callable=AsyncMock) as t3,
        ):
            result = await crawler.crawl_with_metadata("https://example.com")

        t2.assert_awaited_once()
        t3.assert_not_awaited()
        assert result.title == "Tier2 Title"
        assert "Content" in result.markdown

    @pytest.mark.asyncio
    async def test_tier1_import_error_skips_to_tier2(self):
        """Tier 1 raises ImportError (curl_cffi missing) -> skips to Tier 2."""
        crawler = ScraplingCrawler()
        page_t2 = _make_page_mock("Tier2 Title")

        with (
            patch.object(crawler, "_tier1_fetch", new_callable=AsyncMock, side_effect=ImportError("No module named 'curl_cffi'")),
            patch.object(crawler, "_tier2_fetch", new_callable=AsyncMock, return_value=(page_t2, _GOOD_HTML, 200)) as t2,
            patch.object(crawler, "_tier3_fetch", new_callable=AsyncMock) as t3,
        ):
            result = await crawler.crawl_with_metadata("https://example.com")

        t2.assert_awaited_once()
        t3.assert_not_awaited()
        assert result.title == "Tier2 Title"

    @pytest.mark.asyncio
    async def test_tier1_general_exception_escalates_to_tier2(self):
        """Tier 1 raises a general exception -> escalates to Tier 2."""
        crawler = ScraplingCrawler()
        page_t2 = _make_page_mock("Tier2 Title")

        with (
            patch.object(crawler, "_tier1_fetch", new_callable=AsyncMock, side_effect=RuntimeError("connection timeout")),
            patch.object(crawler, "_tier2_fetch", new_callable=AsyncMock, return_value=(page_t2, _GOOD_HTML, 200)) as t2,
            patch.object(crawler, "_tier3_fetch", new_callable=AsyncMock) as t3,
        ):
            result = await crawler.crawl_with_metadata("https://example.com")

        t2.assert_awaited_once()
        t3.assert_not_awaited()
        assert result.title == "Tier2 Title"

    @pytest.mark.asyncio
    async def test_tier2_blocked_escalates_to_tier3(self):
        """Tier 2 returns stealth-blocked content -> escalates to Tier 3 which succeeds."""
        crawler = ScraplingCrawler()
        page_t1 = _make_page_mock()
        page_t2 = _make_page_mock()
        page_t3 = _make_page_mock("Tier3 Title")

        with (
            patch.object(crawler, "_tier1_fetch", new_callable=AsyncMock, return_value=(page_t1, _BLOCKED_HTML, 200)),
            patch.object(crawler, "_tier2_fetch", new_callable=AsyncMock, return_value=(page_t2, _STEALTH_HTML, 200)),
            patch.object(crawler, "_tier3_fetch", new_callable=AsyncMock, return_value=(page_t3, _GOOD_HTML, 200)) as t3,
        ):
            result = await crawler.crawl_with_metadata("https://example.com")

        t3.assert_awaited_once()
        assert result.title == "Tier3 Title"
        assert "Content" in result.markdown

    @pytest.mark.asyncio
    async def test_tier2_exception_escalates_to_tier3(self):
        """Tier 2 raises an exception -> escalates to Tier 3."""
        crawler = ScraplingCrawler()
        page_t3 = _make_page_mock("Tier3 Title")

        with (
            patch.object(crawler, "_tier1_fetch", new_callable=AsyncMock, side_effect=RuntimeError("t1 fail")),
            patch.object(crawler, "_tier2_fetch", new_callable=AsyncMock, side_effect=RuntimeError("playwright crash")),
            patch.object(crawler, "_tier3_fetch", new_callable=AsyncMock, return_value=(page_t3, _GOOD_HTML, 200)) as t3,
        ):
            result = await crawler.crawl_with_metadata("https://example.com")

        t3.assert_awaited_once()
        assert result.title == "Tier3 Title"

    @pytest.mark.asyncio
    async def test_all_tiers_fail_returns_empty(self):
        """All three tiers raise exceptions -> returns empty CrawlOutput."""
        crawler = ScraplingCrawler()

        with (
            patch.object(crawler, "_tier1_fetch", new_callable=AsyncMock, side_effect=RuntimeError("t1")),
            patch.object(crawler, "_tier2_fetch", new_callable=AsyncMock, side_effect=RuntimeError("t2")),
            patch.object(crawler, "_tier3_fetch", new_callable=AsyncMock, side_effect=RuntimeError("t3")),
        ):
            result = await crawler.crawl_with_metadata("https://example.com")

        assert result.title == ""
        assert result.html == ""
        assert result.markdown == ""

    @pytest.mark.asyncio
    async def test_tier3_still_blocked_returns_empty(self):
        """Tier 3 returns stealth-blocked content -> returns empty CrawlOutput."""
        crawler = ScraplingCrawler()
        page_t1 = _make_page_mock()
        page_t2 = _make_page_mock()
        page_t3 = _make_page_mock()

        with (
            patch.object(crawler, "_tier1_fetch", new_callable=AsyncMock, return_value=(page_t1, _BLOCKED_HTML, 200)),
            patch.object(crawler, "_tier2_fetch", new_callable=AsyncMock, return_value=(page_t2, _STEALTH_HTML, 200)),
            patch.object(crawler, "_tier3_fetch", new_callable=AsyncMock, return_value=(page_t3, _STEALTH_HTML, 403)),
        ):
            result = await crawler.crawl_with_metadata("https://example.com")

        assert result.title == ""
        assert result.html == ""
        assert result.markdown == ""

    @pytest.mark.asyncio
    async def test_crawl_delegates_to_crawl_with_metadata(self):
        """crawl() delegates to crawl_with_metadata and returns .markdown."""
        crawler = ScraplingCrawler()
        expected_output = CrawlOutput(title="Title", html="<p>Hi</p>", markdown="Hi there")

        with patch.object(crawler, "crawl_with_metadata", new_callable=AsyncMock, return_value=expected_output) as mock_cwm:
            result = await crawler.crawl("https://example.com")

        mock_cwm.assert_awaited_once_with("https://example.com")
        assert result == "Hi there"


class TestExtractTitle:
    """Tests for _extract_title helper."""

    def test_with_title_element(self):
        page = _make_page_mock("My Page Title")
        assert _extract_title(page) == "My Page Title"

    def test_without_title_element(self):
        """css() returns a node whose .get() is None -> empty string."""
        title_node = MagicMock()
        title_node.get.return_value = None
        page = MagicMock()
        page.css.return_value = title_node
        assert _extract_title(page) == ""

    def test_exception_returns_empty(self):
        """Any exception in css() -> returns empty string."""
        page = MagicMock()
        page.css.side_effect = AttributeError("no css method")
        assert _extract_title(page) == ""

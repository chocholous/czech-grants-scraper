"""Tests for selector utilities."""

import pytest
from bs4 import BeautifulSoup

from grants_scraper.core.selectors import (
    Selector,
    get_main_container,
    cleanup_navigation,
    extract_page_title,
    extract_summary,
    extract_documents,
    classify_document_type,
    is_document_link,
    get_file_format,
    extract_contact_email,
)


@pytest.fixture
def sample_html():
    """Sample HTML for testing."""
    return """
    <html>
    <head><title>Test Page</title></head>
    <body>
        <nav><a href="/menu">Menu</a></nav>
        <main>
            <h1>Test Grant</h1>
            <div class="perex">This is the summary.</div>
            <p>First paragraph with more details.</p>
            <h2>Documents</h2>
            <a href="/docs/vyzva.pdf">Výzva 2024</a>
            <a href="/docs/guidelines.docx">Příručka</a>
            <a href="mailto:info@example.com">Contact</a>
        </main>
        <footer>Footer content</footer>
    </body>
    </html>
    """


@pytest.fixture
def soup(sample_html):
    """Parsed BeautifulSoup fixture."""
    return BeautifulSoup(sample_html, "lxml")


class TestSelector:
    """Tests for Selector class."""

    def test_css_selector(self, soup):
        """Test CSS selector."""
        selector = Selector(soup, "https://example.com")
        result = selector.css("h1")

        assert result.found is True
        assert result.value == "Test Grant"

    def test_css_one_selector(self, soup):
        """Test CSS one selector."""
        selector = Selector(soup, "https://example.com")
        result = selector.css_one(".perex")

        assert result.found is True
        assert result.value == "This is the summary."

    def test_css_selector_not_found(self, soup):
        """Test CSS selector when not found."""
        selector = Selector(soup, "https://example.com")
        result = selector.css(".nonexistent")

        assert result.found is False
        assert result.value is None

    def test_regex_selector(self, soup):
        """Test regex extraction."""
        selector = Selector(soup, "https://example.com")
        result = selector.regex(r"(\d{4})")

        assert result.found is True
        assert result.value == "2024"

    def test_try_selectors(self, soup):
        """Test trying multiple selectors."""
        selector = Selector(soup, "https://example.com")
        result = selector.try_selectors([".nonexistent", ".perex", "p"])

        assert result.found is True
        assert result.value == "This is the summary."


class TestGetMainContainer:
    """Tests for get_main_container function."""

    def test_finds_main(self, soup):
        """Test finding main element."""
        container = get_main_container(soup)
        assert container.name == "main"

    def test_fallback_to_body(self):
        """Test fallback to body when no main."""
        html = "<html><body><p>Content</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        container = get_main_container(soup)
        assert container.name == "body"


class TestCleanupNavigation:
    """Tests for cleanup_navigation function."""

    def test_removes_nav(self, soup):
        """Test nav removal."""
        assert soup.find("nav") is not None
        cleanup_navigation(soup)
        assert soup.find("nav") is None

    def test_removes_footer(self, soup):
        """Test footer removal."""
        assert soup.find("footer") is not None
        cleanup_navigation(soup)
        assert soup.find("footer") is None


class TestExtractPageTitle:
    """Tests for extract_page_title function."""

    def test_extracts_h1(self, soup):
        """Test extracting h1 as title."""
        title = extract_page_title(soup)
        assert title == "Test Grant"

    def test_fallback_to_title_tag(self):
        """Test fallback to title tag."""
        html = "<html><head><title>Page Title</title></head><body></body></html>"
        soup = BeautifulSoup(html, "lxml")
        title = extract_page_title(soup)
        assert title == "Page Title"


class TestExtractSummary:
    """Tests for extract_summary function."""

    def test_extracts_perex(self, soup):
        """Test extracting perex class."""
        container = get_main_container(soup)
        summary = extract_summary(container)
        assert summary == "This is the summary."


class TestExtractDocuments:
    """Tests for extract_documents function."""

    def test_extracts_documents(self, soup):
        """Test document extraction."""
        docs = extract_documents(soup, "https://example.com")

        assert len(docs) == 2
        assert docs[0]["file_format"] == "pdf"
        assert docs[0]["doc_type"] == "call_text"
        assert docs[1]["file_format"] == "docx"


class TestClassifyDocumentType:
    """Tests for classify_document_type function."""

    def test_call_text(self):
        """Test call text classification."""
        assert classify_document_type("Výzva 2024") == "call_text"
        assert classify_document_type("Zadání projektu") == "call_text"

    def test_guidelines(self):
        """Test guidelines classification."""
        assert classify_document_type("Příručka pro žadatele") == "guidelines"
        assert classify_document_type("Metodika") == "guidelines"

    def test_template(self):
        """Test template classification."""
        assert classify_document_type("Vzor žádosti") == "template"
        assert classify_document_type("Formulář") == "template"

    def test_other(self):
        """Test other classification."""
        assert classify_document_type("Random document") == "other"


class TestIsDocumentLink:
    """Tests for is_document_link function."""

    def test_pdf_link(self):
        """Test PDF link detection."""
        assert is_document_link("https://example.com/doc.pdf") is True

    def test_excel_link(self):
        """Test Excel link detection."""
        assert is_document_link("https://example.com/data.xlsx") is True

    def test_html_link(self):
        """Test HTML link is not document."""
        assert is_document_link("https://example.com/page.html") is False


class TestGetFileFormat:
    """Tests for get_file_format function."""

    def test_pdf(self):
        """Test PDF format extraction."""
        assert get_file_format("https://example.com/doc.pdf") == "pdf"

    def test_xlsx(self):
        """Test XLSX format extraction."""
        assert get_file_format("https://example.com/data.XLSX") == "xlsx"

    def test_no_extension(self):
        """Test URL without extension."""
        assert get_file_format("https://example.com/document") == "unknown"


class TestExtractContactEmail:
    """Tests for extract_contact_email function."""

    def test_extracts_mailto(self, soup):
        """Test extracting email from mailto link."""
        email = extract_contact_email(soup)
        assert email == "info@example.com"

    def test_extracts_from_text(self):
        """Test extracting email from text."""
        html = "<p>Contact: test@example.org for info</p>"
        soup = BeautifulSoup(html, "lxml")
        email = extract_contact_email(soup)
        assert email == "test@example.org"

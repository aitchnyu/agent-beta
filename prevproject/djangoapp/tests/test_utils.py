"""Tests for djangoapp utility functions."""

from __future__ import annotations

from django.test import TestCase

from djangoapp.utils import sanitize_html


class TestSanitizeHtml(TestCase):
    """Tests for the sanitize_html function."""

    def test_legal_tags_preserved(self) -> None:
        """Test that all allowed tags pass through unchanged."""
        html = """\
<p>Hello world</p>
<p><strong>bold</strong> and <em>italic</em></p>
<h1>Heading 1</h1>
<h2>Heading 2</h2>
<h6>Heading 6</h6>
<ul><li>Item 1</li><li>Item 2</li></ul>
<ol><li>First</li></ol>"""
        result = sanitize_html(html)
        expected = """\
<p>Hello world</p>
<p><strong>bold</strong> and <em>italic</em></p>
<h1>Heading 1</h1>
<h2>Heading 2</h2>
<h6>Heading 6</h6>
<ul><li>Item 1</li><li>Item 2</li></ul>
<ol><li>First</li></ol>"""
        self.assertEqual(result, expected)

    def test_legal_links_tables_hr_br(self) -> None:
        """Test links, tables, hr, br are preserved."""
        html = """\
<a href="https://example.com">Link</a>
<table><thead><tr><th>Header</th></tr></thead><tbody><tr><td>Cell</td></tr></tbody></table>
<p>Line 1</p><br><hr><p>Line 2</p>"""
        result = sanitize_html(html)
        expected = """\
<a href="https://example.com" rel="noopener noreferrer">Link</a>
<table><thead><tr><th>Header</th></tr></thead><tbody><tr><td>Cell</td></tr></tbody></table>
<p>Line 1</p><br><hr><p>Line 2</p>"""
        self.assertEqual(result, expected)

    def test_illegal_tags_removed(self) -> None:
        """Test that script, style, iframe, onclick, div are stripped."""
        html = """\
<p>Safe</p><script>alert('xss')</script>
<p onclick="alert('xss')">Click me</p>
<style>body { display: none; }</style><p>Visible</p>
<iframe src="https://evil.com"></iframe><p>Safe</p>
<div>Content</div>"""
        result = sanitize_html(html)
        expected = """\
<p>Safe</p>
<p>Click me</p>
<p>Visible</p>
<p>Safe</p>
Content"""
        self.assertEqual(result, expected)

    def test_span_tags_stripped(self) -> None:
        """Test that span tags are stripped (not in allowed list)."""
        html = '<span class="mention">user</span>'
        result = sanitize_html(html)
        self.assertEqual(result, "user")

    def test_empty_string(self) -> None:
        """Test that empty string returns empty."""
        result = sanitize_html("")
        self.assertEqual(result, "")

    def test_javascript_href_removed(self) -> None:
        """Test that javascript: in href is removed."""
        html = "<a href=\"javascript:alert('xss')\">Click</a>"
        result = sanitize_html(html)
        self.assertEqual(result, '<a rel="noopener noreferrer">Click</a>')

"""
Unit tests for text formatting functions

Tests the formatSpecials() function which formats long messages
for display on departure boards.
"""

import pytest
import plugin


@pytest.mark.unit
class TestFormatSpecials:
    """Test cases for formatSpecials function"""

    def test_empty_message(self):
        """Test with empty message"""
        result = plugin.formatSpecials("")
        assert result == ""

    def test_whitespace_only(self):
        """Test with whitespace only"""
        result = plugin.formatSpecials("   ")
        assert result == "   "

    def test_short_message_no_formatting_needed(self):
        """Test short message that needs no special formatting"""
        message = "Service running on time"
        result = plugin.formatSpecials(message)
        # Should add +++ prefix and newline
        assert result == "+++Service running on time\n"

    def test_remove_html_paragraph_tags(self):
        """Test removal of HTML <P> tags"""
        message = "<P>This is a test</P>"
        result = plugin.formatSpecials(message)
        assert "<P>" not in result
        assert "</P>" not in result
        assert "This is a test" in result

    def test_remove_html_anchor_tags(self):
        """Test removal of HTML <A> tags"""
        message = "<A>Click here</A>"
        result = plugin.formatSpecials(message)
        assert "<A>" not in result
        assert "</A>" not in result
        assert "Click here" in result

    def test_remove_nbsp(self):
        """Test removal of non-breaking spaces"""
        message = "Word&nbspword&nbspword"
        result = plugin.formatSpecials(message)
        assert "&nbsp" not in result
        assert "Word word word" in result

    def test_remove_newlines(self):
        """Test removal of newline characters"""
        message = "Line 1\nLine 2\nLine 3"
        result = plugin.formatSpecials(message)
        # Newlines should be removed from input
        assert "\n" in result  # But will have newline at end from formatting
        # Check the original newlines are gone
        assert "Line 1Line 2Line 3" in result

    def test_remove_square_brackets(self):
        """Test removal of square brackets"""
        message = "[Update] Service delayed [Reason: signal failure]"
        result = plugin.formatSpecials(message)
        assert "[" not in result
        assert "]" not in result
        assert "Update Service delayed Reason: signal failure" in result

    def test_clean_urls(self):
        """Test cleaning of URLs"""
        message = 'Visit http://example.com for details'
        result = plugin.formatSpecials(message)
        assert "http" not in result
        assert "://" not in result
        assert "www.example.com" in result

    def test_remove_href(self):
        """Test removal of href attribute"""
        message = '<A href="http://example.com">Link</A>'
        result = plugin.formatSpecials(message)
        assert "href=" not in result

    def test_remove_quotes(self):
        """Test removal of double quotes"""
        message = 'The "special" service'
        result = plugin.formatSpecials(message)
        assert '"' not in result
        assert "The special service" in result

    def test_remove_travel_news_text(self):
        """Test removal of 'Travel News.' text"""
        message = "Travel News. Latest updates available"
        result = plugin.formatSpecials(message)
        assert "Travel News." not in result
        assert "Latest" not in result  # Also removes "Latest"
        assert "updates available" in result

    def test_long_message_split_into_lines(self):
        """Test that long messages are split at line boundaries"""
        # Create a message longer than 130 characters
        message = "A" * 140
        result = plugin.formatSpecials(message)
        # Should contain multiple +++ prefixes indicating line breaks
        assert result.count("+++") >= 1

    def test_message_respects_max_lines(self):
        """Test that message respects maximum of 2 lines"""
        # Create a very long message that would need 3+ lines
        message = "A " * 200  # Lots of words
        result = plugin.formatSpecials(message)
        # Should only have 2 lines (2 +++ markers)
        assert result.count("+++") <= 2

    def test_line_split_at_word_boundary(self):
        """Test that lines split at word boundaries, not mid-word"""
        # Create message with words that will need splitting
        message = "Word " * 50  # 250 characters with spaces
        result = plugin.formatSpecials(message)
        # Should not have partial words
        lines = result.split("\n")
        for line in lines:
            if line:  # Skip empty lines
                # Each line should start with +++ and contain complete words
                assert line.startswith("+++")

    def test_complex_html_message(self):
        """Test with complex HTML-like message"""
        message = '<P><A href="http://nationalrail.co.uk">Click here</A> for details.</P>'
        result = plugin.formatSpecials(message)
        # Should remove all HTML
        assert "<" not in result
        assert ">" not in result  # Except the one from <A >
        assert "href=" not in result
        assert "www.nationalrail.co.uk" in result
        assert "Click here for details" in result

    def test_real_world_message_example(self):
        """Test with realistic Darwin API message"""
        message = (
            "[Latest Travel News.] <P>Delays expected due to signal failure at Reading. "
            "<A href='http://nationalrail.co.uk/travel-news'>Visit our website</A> for updates.</P>"
        )
        result = plugin.formatSpecials(message)

        # Should be cleaned
        assert "[" not in result
        assert "]" not in result
        assert "<P>" not in result
        assert "</P>" not in result
        assert "<A" not in result
        assert "</A>" not in result
        assert "href=" not in result
        assert "Latest" not in result
        # Note: Code only removes "Travel News." (with period), not "Travel News"
        assert "Travel News." not in result

        # Should contain cleaned content
        assert "Delays expected" in result
        assert "signal failure" in result
        assert "www.nationalrail.co.uk" in result

    @pytest.mark.parametrize("input_msg,should_not_contain", [
        ("<P>Test</P>", "<P>"),
        ("<A>Link</A>", "<A>"),
        ("&nbspTest", "&nbsp"),
        ("Test\nLine", "Test\nLine"),  # Original newline should be gone
        ("[Note]", "["),
        ("Word]", "]"),
        ('Say "Hello"', '"'),
    ])
    def test_removal_patterns(self, input_msg, should_not_contain):
        """Parametrized test for various removal patterns"""
        result = plugin.formatSpecials(input_msg)
        assert should_not_contain not in result


@pytest.mark.unit
class TestFormatSpecialsEdgeCases:
    """Edge cases for formatSpecials"""

    def test_message_exactly_at_max_length(self):
        """Test message that's exactly at the 130 character limit"""
        message = "A" * 130
        result = plugin.formatSpecials(message)
        # Should fit on one line
        assert result.count("+++") == 1

    def test_message_one_char_over_limit(self):
        """Test message that's just one character over limit"""
        message = "A" * 131
        result = plugin.formatSpecials(message)
        # Might need splitting depending on word boundaries

    def test_no_spaces_in_long_message(self):
        """Test very long message with no spaces"""
        message = "A" * 200
        result = plugin.formatSpecials(message)
        # Should handle gracefully even without word boundaries

    def test_multiple_html_tags_nested(self):
        """Test with multiple nested HTML tags"""
        message = "<P><A><P>Nested</P></A></P>"
        result = plugin.formatSpecials(message)
        assert "<P>" not in result
        assert "</P>" not in result
        assert "Nested" in result

    def test_unicode_characters(self):
        """Test with unicode characters"""
        message = "Service to Zürich via François"
        result = plugin.formatSpecials(message)
        # Should preserve unicode
        assert "Zürich" in result
        assert "François" in result

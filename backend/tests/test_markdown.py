from app.services.markdown import md_to_html, md_to_plain, md_to_whatsapp


def test_html_renders_bold():
    assert "<strong>x</strong>" in md_to_html("**x**")


def test_html_linkify():
    assert "<a href" in md_to_html("visit https://example.com")


def test_whatsapp_bold_conversion():
    assert md_to_whatsapp("**hello** world") == "*hello* world"


def test_whatsapp_strips_heading_marker():
    assert md_to_whatsapp("# Title\n\nbody") == "Title\n\nbody"


def test_whatsapp_preserves_italic_and_strike():
    # Single underscore/tilde pass through — WA supports them natively
    assert "_italic_" in md_to_whatsapp("_italic_")
    assert "~gone~" in md_to_whatsapp("~gone~")


def test_whatsapp_link_format():
    out = md_to_whatsapp("[click](https://x.y)")
    assert out == "click (https://x.y)"


def test_whatsapp_strips_html():
    assert md_to_whatsapp("hello <b>world</b>") == "hello world"


def test_plain_strips_everything():
    s = "# Title\n\n**bold** _italic_ ~strike~ `code`\n[link](http://x)"
    out = md_to_plain(s)
    assert "#" not in out
    assert "**" not in out
    assert "`" not in out
    assert "bold" in out
    assert "italic" in out

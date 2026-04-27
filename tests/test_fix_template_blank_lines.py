from utils.regex_patterns import fix_template_blank_lines


def test_single_line_cite_web_unchanged():
    text = "{{cite web|title=Foo|url=http://example.com}}"
    assert fix_template_blank_lines(text) == text


def test_single_line_sfn_unchanged():
    text = "{{sfn|Author|2020|p=42}}"
    assert fix_template_blank_lines(text) == text


def test_single_line_lang_unchanged():
    text = "{{Lang-ar|محمد}}"
    assert fix_template_blank_lines(text) == text


def test_multiline_template_first_param_on_new_line():
    text = "{{Infobox religious biography\n| name = Sharif\n}}"
    result = fix_template_blank_lines(text)
    assert result.startswith("{{Infobox religious biography\n|")


def test_nested_single_line_template_untouched():
    text = "{{Infobox| name = {{lang|ar|محمد}}\n| title = Y\n}}"
    result = fix_template_blank_lines(text)
    assert "{{lang|ar|محمد}}" in result
    assert result.startswith("{{Infobox\n| name")
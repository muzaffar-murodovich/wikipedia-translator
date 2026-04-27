from utils.regex_patterns import apply_all_fixes


def test_infobox_param_no_extra_period():
    """Infobox parametri ichidagi <ref> dan keyin nuqta qoʻshilmasligi kerak."""
    text = "{{Shaxs bilgiqutisi|death_date=1044<ref>manba</ref>}}"
    result = apply_all_fixes(text)
    assert "</ref>." not in result
    assert "</ref>}}" in result


def test_normal_sentence_gets_period():
    """Oddiy jumladagi <ref> dan keyin nuqta qoʻshilishi kerak."""
    text = "Bu jumla<ref>manba</ref>\nKeyingi qator"
    result = apply_all_fixes(text)
    assert "</ref>." in result
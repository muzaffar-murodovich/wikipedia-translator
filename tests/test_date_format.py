from utils.regex_patterns import _apply_date_fixes

# Rule 5a tests1
assert _apply_date_fixes("132 hijriy") == "hijriy 132-yil"
assert _apply_date_fixes("750 milodiy") == "milodiy 750-yil"
assert _apply_date_fixes("132 hijriy/750 milodiy") == "hijriy 132-yil/milodiy 750-yil"
assert _apply_date_fixes("hijriy 132") == "hijriy 132-yil"

# Idempotent — toʻgʻri formatlangan matn oʻzgarmasligi kerak
assert _apply_date_fixes("hijriy 132-yil") == "hijriy 132-yil"
assert _apply_date_fixes("milodiy 750-yil") == "milodiy 750-yil"

# Aralash holat: arab nomi + sana
text = "al-Tabariy 132 hijriy yilda tugʻilgan"
assert _apply_date_fixes(text) == "at-Tabariy hijriy 132-yilda tugʻilgan"

# Manba ichida tegmaslik
text = "Maʼlumot.<ref>132 hijriy yilda</ref>"
result = _apply_date_fixes(text)
assert "132 hijriy yilda" in result  # ref ichi tegilmagan

# Infobox parametri tuzatiladi
text = "{{Shaxs bilgiqutisi|birth_year=132 hijriy}}"
result = _apply_date_fixes(text)
assert "birth_year=hijriy 132-yil" in result
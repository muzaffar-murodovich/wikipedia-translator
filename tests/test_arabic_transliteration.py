from utils.regex_patterns import fix_arabic_transliteration

# Infobox — parametrlar TUZATILADI
text = "{{Shaxs bilgiqutisi|name=Muḥammad|birth_place=al-Madīna}}"
result = fix_arabic_transliteration(text)
assert "name=Muhammad" in result
assert "birth_place=al-Madina" in result

# Katta-kichik harfga sezgir emas
text = "{{Joyni Bilgiqutisi|name=al-Ṭabariyyah}}"
result = fix_arabic_transliteration(text)
assert "name=at-Tabariyyah" in result

# cite book — TEGILMAYDI
text = "{{cite book|author=Muḥammad ibn Isḥāq|title=Sirah}}"
assert fix_arabic_transliteration(text) == text

# sfn — TEGILMAYDI
text = "{{sfn|al-Ṭabarī|2010|p=42}}"
assert fix_arabic_transliteration(text) == text

# lang-* — TEGILMAYDI (asl tildagi matn saqlanadi)
text = "{{lang-ar|Muḥammad}}"
assert fix_arabic_transliteration(text) == text

# <ref> ichidagi hamma narsa tegilmaydi (ref qoidasi ustunroq)
text = "<ref>{{Shaxs bilgiqutisi|name=Muḥammad}}</ref>"
assert fix_arabic_transliteration(text) == text

# Aralash holat: infobox + asosiy matn + manba
text = (
    "{{Shaxs bilgiqutisi|name=Muḥammad|birth_year=570}}\n"
    "'''Muḥammad''' — payg'ambar.<ref>{{cite book|author=Ibn Isḥāq}}</ref>"
)
result = fix_arabic_transliteration(text)
assert "name=Muhammad" in result          # infobox tuzatilgan
print(repr(result))
assert "'''Muhammad''' — pay" in result   # asosiy matn tuzatilgan
assert "Ibn Isḥāq" in result              # ref + cite ichi tegilmagan
import re

wikitext = "1997 yilgan"

wikitext = re.sub(r'(\d+)\s+(yil(?:da|lar(?:i|da)?)?)', r'\1-\2', wikitext)

print(wikitext)
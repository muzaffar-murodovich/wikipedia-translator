import pywikibot


def check_category_translations(category_name, target_lang="uz"):
    # Inglizcha sayt
    en_site = pywikibot.Site("en", "wikipedia")
    target_site = pywikibot.Site(target_lang, "wikipedia")

    category = pywikibot.Category(en_site, f"{category_name}")

    print(f"Checking Category:{category_name}\n")

    found = 0
    not_found = 0

    for page in category.articles():
        try:
            # Interwiki linklarni olish
            langlinks = page.langlinks()
            translation = None

            for link in langlinks:
                if link.site.code == target_lang:
                    translation = link.title
                    break

            # Brauzer uchun to'g'ridan-to'g'ri URL
            en_url = page.full_url()

            if translation:
                found += 1
                target_url = target_site.base_url(f"/wiki/{translation.replace(' ', '_')}")
                # print(f"✅ {en_url} → {target_url}")
            else:
                not_found += 1
                print(f"❌ {en_url}")

        except Exception as e:
            print(f"⚠️ Error with {page.title()}: {e}")

    print("\n--- SUMMARY ---")
    print(f"Found in {target_lang}: {found}")
    print(f"Not found: {not_found}")


category = "Category:8th-century people from the Umayyad Caliphate"
if __name__ == "__main__":
    check_category_translations(category, target_lang="uz")

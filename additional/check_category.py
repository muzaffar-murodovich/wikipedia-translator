import asyncio
import aiohttp
import pywikibot
from typing import Dict, List, Set
import json
from concurrent.futures import ThreadPoolExecutor


class WikipediaArticleChecker:
    def __init__(self, source_lang: str = "en", target_langs: List[str] = None):
        """
        Initialize the checker with source and target languages.
        
        Args:
            source_lang: Source language code (default: "en" for English)
            target_langs: List of target language codes (default: ["uz"] for Uzbek)
        """
        self.source_lang = source_lang
        self.target_langs = target_langs or ["uz"]
        
        # Initialize pywikibot sites for each language
        self.sites = {
            source_lang: pywikibot.Site(source_lang, 'wikipedia')
        }
        for lang in self.target_langs:
            self.sites[lang] = pywikibot.Site(lang, 'wikipedia')
    
    def get_category_members_sync(self, category: str, lang: str = None) -> List[str]:
        """
        Fetch all articles in a Wikipedia category using pywikibot.
        
        Args:
            category: Category name (without "Category:" prefix)
            lang: Language code
        
        Returns:
            List of article titles in the category
        """
        lang = lang or self.source_lang
        site = self.sites[lang]
        
        try:
            cat = pywikibot.Category(site, f"Category:{category}")
            articles = []
            
            print(f"Fetching articles from '{category}' in {lang} Wikipedia...")
            
            # Iterate through category members
            for member in cat.members(namespaces=0):  # namespace 0 is articles
                if isinstance(member, pywikibot.Page) and not member.isRedirectPage():
                    articles.append(member.title())
            
            return articles
        
        except pywikibot.exceptions.Error as e:
            print(f"Error fetching category '{category}' from {lang} Wikipedia: {e}")
            return []
    
    def check_article_exists_sync(self, article: str, lang: str) -> tuple:
        """
        Check if an article exists in a specific language Wikipedia using pywikibot.
        
        Args:
            article: Article title
            lang: Language code
        
        Returns:
            Tuple of (exists: bool, article_title: str or None)
        """
        try:
            site = self.sites[lang]
            page = pywikibot.Page(site, article)
            
            # Check if page exists and is not a redirect
            if page.exists():
                return (True, page.title())
            return (False, None)
        
        except pywikibot.exceptions.Error as e:
            print(f"Error checking article '{article}' in {lang}: {e}")
            return (False, None)
    
    async def get_category_members_async(self, category: str) -> List[str]:
        """
        Fetch category members asynchronously using thread pool.
        
        Args:
            category: Category name
        
        Returns:
            List of article titles
        """
        loop = asyncio.get_event_loop()
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            articles = await loop.run_in_executor(
                executor,
                self.get_category_members_sync,
                category,
                self.source_lang
            )
        
        return articles
    
    async def check_articles_in_languages_async(self, articles: List[str]) -> Dict[str, Dict[str, str]]:
        """
        Check which articles exist in target language Wikipedias asynchronously.
        
        Args:
            articles: List of article titles
        
        Returns:
            Dictionary with article titles and their titles in target languages (or "✗" if not found)
        """
        results = {article: {lang: "✗" for lang in self.target_langs} for article in articles}
        
        loop = asyncio.get_event_loop()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            tasks = []
            
            for article in articles:
                for lang in self.target_langs:
                    task = loop.run_in_executor(
                        executor,
                        self.check_article_exists_sync,
                        article,
                        lang
                    )
                    tasks.append((article, lang, task))
            
            # Gather all results
            for article, lang, task in tasks:
                try:
                    exists, title = await task
                    results[article][lang] = title if exists else "✗"
                except Exception as e:
                    print(f"Error processing {article} in {lang}: {e}")
                    results[article][lang] = "✗"
        
        return results
    
    async def run(self, category: str) -> Dict[str, Dict[str, bool]]:
        """
        Main method to fetch articles and check their existence across languages.
        
        Args:
            category: Wikipedia category name
        
        Returns:
            Results dictionary with article existence across languages
        """
        # Fetch articles from source language category
        articles = await self.get_category_members_async(category)
        
        if not articles:
            print(f"No articles found in category '{category}'")
            return {}
        
        print(f"Found {len(articles)} articles in the category")
        print(f"Checking availability in: {', '.join(self.target_langs)}...")
        
        # Check articles in target languages
        results = await self.check_articles_in_languages_async(articles)
        
        return results
    
    def print_results(self, results: Dict[str, Dict[str, str]]):
        """Pretty print the results."""
        if not results:
            print("No results to display.")
            return
        
        print("\n" + "="*120)
        print("RESULTS")
        print("="*120 + "\n")
        
        # Print header
        header = "Article Name" + " " * 58 + "|"
        for lang in self.target_langs:
            header += f" {lang} |"
        print(header)
        print("-"*120)
        
        # Print results
        for article, langs_status in sorted(results.items()):
            row = f"{article:<70} |"
            for lang in self.target_langs:
                title = langs_status[lang]
                row += f" {title:<20} |"
            print(row)
        
        print("\n" + "="*120)
        print("SUMMARY")
        print("="*120)
        
        for lang in self.target_langs:
            count = sum(1 for article_langs in results.values() if article_langs[lang] != "✗")
            total = len(results)
            percentage = (count / total * 100) if total > 0 else 0
            print(f"{lang.upper()}: {count}/{total} articles ({percentage:.1f}%)")
    
    def save_results(self, results: Dict[str, Dict[str, bool]], filename: str = "wikipedia_results.json"):
        """Save results to JSON file."""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\nResults saved to {filename}")
        except Exception as e:
            print(f"Error saving results: {e}")


async def main():
    """Example usage."""
    # Initialize checker for English to Uzbek and Russian
    checker = WikipediaArticleChecker(source_lang="en", target_langs=["uz"])

    # Run the check for a specific category
    # Change "Mathematics" to any Wikipedia category
    results = await checker.run("5th-century Arab people")
    
    # Print results
    checker.print_results(results)
    
    # Save results to JSON
    checker.save_results(results)


if __name__ == "__main__":
    # Configure pywikibot (optional)
    # You can set up a pywikibot config file or it will use defaults
    
    asyncio.run(main())
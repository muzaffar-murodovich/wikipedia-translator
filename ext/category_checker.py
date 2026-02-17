#!/usr/bin/env python3
"""
Compare articles in an English Wikipedia category with Uzbek Wikipedia.
Checks which articles exist on both wikis.
Requires: pywikibot library (install with: pip install pywikibot)
"""

import pywikibot
from pywikibot import Category, Page


def check_category_articles(category_name):
    """
    Check articles from an English Wikipedia category and find which exist on Uzbek Wikipedia.
    
    Args:
        category_name (str): Name of the category on English Wikipedia (with or without "Category:" prefix)
    
    Returns:
        dict: Dictionary with article comparison results
    """
    # Connect to both Wikipedia sites
    en_site = pywikibot.Site('en', 'wikipedia')
    uz_site = pywikibot.Site('uz', 'wikipedia')
    
    # Ensure category name has proper prefix for English Wikipedia
    if not category_name.startswith('Category:'):
        category_name = f'Category:{category_name}'
    
    result = {
        'category_name': category_name,
        'total_articles_en': 0,
        'total_articles_uz': 0,
        'articles': [],
        'success': False,
        'error': None
    }
    
    try:
        # Create category object for English Wikipedia
        en_category = Category(en_site, category_name)
        
        # Check if category exists
        if not en_category.exists():
            result['error'] = f"Category '{category_name}' does not exist on English Wikipedia."
            return result
        
        print(f"Fetching articles from '{category_name}'...")
        
        # Get all articles from the category (namespace 0 = main article namespace)
        en_articles = list(en_category.articles(namespaces=0))
        result['total_articles_en'] = len(en_articles)
        
        if result['total_articles_en'] == 0:
            result['error'] = f"Category '{category_name}' contains no articles."
            return result
        
        print(f"Found {result['total_articles_en']} articles. Checking Uzbek Wikipedia...\n")
        
        # Check each article on Uzbek Wikipedia
        for i, en_article in enumerate(en_articles, 1):
            article_title = en_article.title()
            print(f"Checking {i}/{result['total_articles_en']}: {article_title}...", end='\r')
            
            article_info = {
                'title': article_title,
                'exists_uz': False,
                'uz_title': None
            }
            
            # Try to get the Uzbek Wikipedia equivalent using interwiki links
            try:
                # Get interwiki links
                if 'uz' in en_article.langlinks():
                    uz_link = en_article.langlinks()['uz']
                    article_info['exists_uz'] = True
                    article_info['uz_title'] = uz_link.title
                    result['total_articles_uz'] += 1
            except:
                # If langlinks fail, article doesn't exist on Uzbek Wikipedia
                pass
            
            result['articles'].append(article_info)
        
        print(" " * 80)  # Clear the progress line
        result['success'] = True
        return result
        
    except Exception as e:
        result['error'] = f"Error: {str(e)}"
        return result


def display_results(result):
    """Display the comparison results in a formatted way."""
    
    print("=" * 80)
    print(f"CATEGORY: {result['category_name']}")
    print("=" * 80)
    
    if result['error']:
        print(f"❌ {result['error']}")
        return
    
    print(f"\nTotal articles in English Wikipedia: {result['total_articles_en']}")
    print(f"Total articles found in Uzbek Wikipedia: {result['total_articles_uz']}")
    
    if result['total_articles_en'] > 0:
        percentage = (result['total_articles_uz'] / result['total_articles_en']) * 100
        print(f"Coverage: {percentage:.1f}%")
    
    print("\n" + "=" * 80)
    print("ARTICLES:")
    print("=" * 80)
    
    for article in result['articles']:
        status = "✅" if article['exists_uz'] else "❌"
        print(f"{article['title']} {status}")
        if article['exists_uz'] and article['uz_title'] != article['title']:
            print(f"  → Uzbek title: {article['uz_title']}")
    
    print("=" * 80)


def save_results_to_file(result, filename="category_comparison.txt"):
    """Save results to a text file."""
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write(f"CATEGORY: {result['category_name']}\n")
        f.write("=" * 80 + "\n\n")
        
        if result['error']:
            f.write(f"❌ {result['error']}\n")
            return filename
        
        f.write(f"Total articles in English Wikipedia: {result['total_articles_en']}\n")
        f.write(f"Total articles found in Uzbek Wikipedia: {result['total_articles_uz']}\n")
        
        if result['total_articles_en'] > 0:
            percentage = (result['total_articles_uz'] / result['total_articles_en']) * 100
            f.write(f"Coverage: {percentage:.1f}%\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("ARTICLES:\n")
        f.write("=" * 80 + "\n")
        
        for article in result['articles']:
            status = "✅" if article['exists_uz'] else "❌"
            f.write(f"{article['title']} {status}\n")
            if article['exists_uz'] and article['uz_title'] != article['title']:
                f.write(f"  → Uzbek title: {article['uz_title']}\n")
        
        f.write("=" * 80 + "\n")
    
    return filename

category_name = "8th-century Arab people"  # Example category name for testing

def main():
    """Main function to demonstrate usage."""
    print("=" * 80)
    print("English to Uzbek Wikipedia Category Comparison")
    print("=" * 80)
    
    # Get category name from user
    # category_name = input("\nEnter English Wikipedia category name (e.g., '8th-century Arab people'): ").strip()
    
    if not category_name:
        print("Error: Category name cannot be empty.")
        return
    
    print()
    result = check_category_articles(category_name)
    
    print()
    display_results(result)

if __name__ == "__main__":
    main()
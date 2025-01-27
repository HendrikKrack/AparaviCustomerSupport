import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from dotenv import load_dotenv

# Load environment variables from root directory
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(root_dir, '.env')
load_dotenv(env_path)

# Get credentials from environment variables
APARAVI_EMAIL = os.getenv('APARAVI_EMAIL')
APARAVI_PASSWORD = os.getenv('APARAVI_PASSWORD')

if not APARAVI_EMAIL or not APARAVI_PASSWORD:
    raise ValueError("APARAVI_EMAIL or APARAVI_PASSWORD not found in environment variables")

def login_to_aparavi():
    session = requests.Session()
    login_url = "https://aparavi-academy.eu/en/login"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    
    login_data = {
        'email': APARAVI_EMAIL,
        'password': APARAVI_PASSWORD
    }
    
    try:
        response = session.post(login_url, data=login_data, headers=headers)
        if response.ok:
            print("Successfully logged in!")
            return session
        else:
            print(f"Login failed with status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Login error: {e}")
        return None

def crawl_page(session, url):
    try:
        # Check if the URL is within the allowed domain and is an English page
        if not url.startswith("https://aparavi-academy.eu") or not ("/en/" in url or url.endswith("/en")):
            return []
            
        response = session.get(url, timeout=10)  # Added timeout
        if not response.ok:
            print(f"Failed to fetch {url}: Status code {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.content, "html.parser")
        links = []
        for link in soup.find_all("a", href=True):
            next_url = urljoin(url, link["href"])
            # Only add URLs that are within the allowed domain and are English pages
            if next_url.startswith("https://aparavi-academy.eu") and ("/en/" in next_url or next_url.endswith("/en")):
                links.append(next_url)
        return links
    except requests.exceptions.RequestException as e:
        print(f"Error crawling {url}: {e}")
        return []

def save_urls_to_file(urls, filename='crawled_urls.json'):
    """Safely save URLs to a JSON file with error handling."""
    try:
        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(current_dir, filename)

        # Create a backup of existing file if it exists
        if os.path.exists(filepath):
            backup_name = f"{filepath}.backup"
            try:
                os.replace(filepath, backup_name)
                print(f"Created backup of existing file: {backup_name}")
            except OSError as e:
                print(f"Warning: Could not create backup file: {e}")

        # Write to a temporary file first
        temp_filename = f"{filepath}.tmp"
        with open(temp_filename, 'w', encoding='utf-8') as f:
            json.dump(list(urls), f, indent=4, ensure_ascii=False)
        
        # If write was successful, rename temp file to target file
        os.replace(temp_filename, filepath)
        print(f"Successfully saved {len(urls)} URLs to {filepath}")
        return True
    except Exception as e:
        print(f"Error saving URLs to file: {e}")
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except:
                pass
        return False

def main():
    # Initialize the crawler with login session
    base_url = "https://aparavi-academy.eu/en"
    session = login_to_aparavi()

    if not session:
        print("Could not start crawling due to login failure")
        return

    try:
        visited_urls = set()
        urls_to_visit = [base_url]

        while urls_to_visit:
            try:
                current_url = urls_to_visit.pop(0)
                if current_url not in visited_urls:
                    print(f"Crawling: {current_url}")
                    new_links = crawl_page(session, current_url)
                    visited_urls.add(current_url)
                    # Only add new URLs that haven't been visited
                    urls_to_visit.extend([url for url in new_links if url not in visited_urls])
            except Exception as e:
                print(f"Error processing URL {current_url}: {e}")
                continue

        print("Crawling finished.")
        print(f"Total pages crawled: {len(visited_urls)}")
        
        # Save the results
        if visited_urls:
            save_urls_to_file(visited_urls)
        else:
            print("No URLs were crawled, skipping file save")

    except Exception as e:
        print(f"An error occurred during crawling: {e}")
    finally:
        if session:
            try:
                session.close()
            except:
                pass

if __name__ == "__main__":
    main()
import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from dotenv import load_dotenv
from webScraper import login_to_aparavi
import json

# Load environment variables from root directory
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(root_dir, '.env')
load_dotenv(env_path)

# Get credentials from environment variables
APARAVI_EMAIL = os.getenv('APARAVI_EMAIL')
APARAVI_PASSWORD = os.getenv('APARAVI_PASSWORD')

if not APARAVI_EMAIL or not APARAVI_PASSWORD:
    raise ValueError("APARAVI_EMAIL or APARAVI_PASSWORD not found in environment variables")

def download_pdf(session, url, output_dir):
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get the page content
        response = session.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Look for PDF links in the page
        pdf_mapping = {}  # Dictionary to store PDF file paths and their source URLs
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.endswith('.pdf'):
                pdf_url = urljoin(url, href)
                try:
                    # Extract filename from URL
                    filename = pdf_url.split('/')[-1]
                    filepath = os.path.join(output_dir, filename)
                    
                    # Download the PDF
                    print(f"Downloading PDF: {pdf_url}")
                    pdf_response = session.get(pdf_url, stream=True)
                    
                    if pdf_response.ok:
                        with open(filepath, 'wb') as f:
                            for chunk in pdf_response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        print(f"Successfully downloaded: {filename}")
                        # Store the mapping of PDF file to source URL
                        pdf_mapping[filepath] = {
                            'source_url': url,
                            'pdf_url': pdf_url
                        }
                    else:
                        print(f"Failed to download {pdf_url}: Status code {pdf_response.status_code}")
                    
                    # Add a small delay to avoid overwhelming the server
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"Error downloading {pdf_url}: {str(e)}")
                    continue
                    
        return pdf_mapping
        
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        return {}

def save_pdf_mapping(mapping, filename='pdf_sources.json'):
    """Save the PDF mapping to a JSON file."""
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=4, ensure_ascii=False)
        print(f"\nPDF source mapping saved to: {filepath}")
    except Exception as e:
        print(f"Error saving PDF mapping: {e}")

def main():
    # Set up the output directory for PDFs
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_pdfs")
    
    # Login to Aparavi
    session = login_to_aparavi()
    if not session:
        print("Login failed!")
        return
    
    print("Successfully logged in. Starting PDF download...")
    
    # Load URLs from crawled_urls.json in the same directory
    urls_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crawled_urls.json")
    try:
        with open(urls_file, 'r') as f:
            urls = json.load(f)
    except FileNotFoundError:
        print(f"Error: {urls_file} not found. Please run webScraper.py first to generate the URLs file.")
        return
    except json.JSONDecodeError:
        print(f"Error: {urls_file} is not a valid JSON file.")
        return
    
    # Process each URL and collect PDF mappings
    total_pdfs = 0
    all_pdf_mappings = {}
    
    for i, url in enumerate(urls, 1):
        print(f"\nProcessing URL {i}/{len(urls)}: {url}")
        pdf_mapping = download_pdf(session, url, output_dir)
        all_pdf_mappings.update(pdf_mapping)
        total_pdfs += len(pdf_mapping)
        
        # Add a small delay between pages
        time.sleep(2)
    
    # Save the PDF source mapping
    save_pdf_mapping(all_pdf_mappings)
    
    print(f"\nDownload complete! Total PDFs found: {total_pdfs}")
    print(f"PDFs have been saved to: {output_dir}")

if __name__ == "__main__":
    main()

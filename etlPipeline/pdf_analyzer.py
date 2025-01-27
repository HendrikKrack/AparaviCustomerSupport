import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import os
from dotenv import load_dotenv
from webScraper import login_to_aparavi

# Load environment variables
load_dotenv()

def analyze_page(session, url):
    try:
        print(f"\nAnalyzing page: {url}")
        response = session.get(url, timeout=10)
        if not response.ok:
            print(f"Failed to fetch page: Status code {response.status_code}")
            return
            
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Look for potential PDF containers or buttons
        print("\nSearching for PDF-related elements...")
        
        # Look for buttons or links with PDF-related text
        pdf_elements = soup.find_all(lambda tag: tag.name in ['a', 'button'] and 
                                   any(pdf_text in tag.get_text().lower() 
                                       for pdf_text in ['pdf', 'download', 'document']))
        
        print("\nPotential PDF-related elements found:")
        for elem in pdf_elements:
            print("\nElement:")
            print(f"Tag: {elem.name}")
            print(f"Text: {elem.get_text().strip()}")
            print(f"Classes: {elem.get('class', [])}")
            print(f"ID: {elem.get('id', 'No ID')}")
            print(f"Href/Link: {elem.get('href', elem.get('onclick', 'No direct link'))}")
            
        # Look for iframes that might embed PDFs
        iframes = soup.find_all('iframe')
        if iframes:
            print("\nFound iframes that might contain PDFs:")
            for iframe in iframes:
                print(f"Src: {iframe.get('src', 'No src')}")
                print(f"Classes: {iframe.get('class', [])}")
                
        # Look for div containers that might hold PDFs
        pdf_containers = soup.find_all('div', class_=lambda x: x and any(pdf_class in x.lower() 
                                     for pdf_class in ['pdf', 'document', 'viewer']))
        if pdf_containers:
            print("\nFound potential PDF containers:")
            for container in pdf_containers:
                print(f"ID: {container.get('id', 'No ID')}")
                print(f"Classes: {container.get('class', [])}")
                
        # Look for any script tags that might handle PDF loading
        pdf_scripts = soup.find_all('script', string=lambda s: s and any(pdf_text in s.lower() 
                                  for pdf_text in ['pdf', '.pdf', 'document']))
        if pdf_scripts:
            print("\nFound scripts that might handle PDFs:")
            for script in pdf_scripts:
                print(f"Script content preview: {script.string[:200] if script.string else 'No inline content'}")
                
    except Exception as e:
        print(f"Error analyzing page: {str(e)}")

def main():
    session = login_to_aparavi()
    if not session:
        print("Login failed!")
        return
        
    # Test with one URL first
    test_url = "https://aparavi-academy.eu/en/technical-documentation/file-categories/system"
    analyze_page(session, test_url)

if __name__ == "__main__":
    main()

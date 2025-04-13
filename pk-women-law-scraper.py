import requests
from bs4 import BeautifulSoup
import re
import os
import time
from googlesearch import search
import PyPDF2


def extract_federal_laws(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def extract_nested_text(element, level=0):
        laws = []
        if element.name in ['li', 'p', 'div']:
            text = element.get_text(separator=' ', strip=True)
            if any(k in text for k in ['Act', 'Ordinance', 'Law', 'Bill', 'Amendment']) and len(text) > 5:
                laws.append(('  ' * level) + text)

        for child in element.find_all(['ul', 'ol', 'li', 'div'], recursive=False):
            laws.extend(extract_nested_text(child, level + 1))

        return laws

    try:
        print(f"Fetching content from {url}...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        main_heading = None
        for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            text = h.get_text().strip()
            if "Federal" in text and ("Laws" in text or "Law" in text):
                main_heading = h
                break

        federal_laws = []

        if main_heading:
            current_element = main_heading.find_next_sibling()
            while current_element:
                if current_element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    if any(province in current_element.get_text().lower() for province in ['punjab', 'sindh', 'sind', 'balochistan', 'khyber', 'gilgit']):
                        break
                if current_element.name in ['ul', 'ol', 'div']:
                    federal_laws.extend(extract_nested_text(current_element))
                current_element = current_element.find_next_sibling()
        else:
            print("No heading found. Falling back to generic list search...")
            for container in soup.find_all(['ul', 'ol', 'div']):
                federal_laws.extend(extract_nested_text(container))


        cleaned_laws = []
        valid_keywords = ['act', 'law', 'bill', 'ordinance', 'amendment']

        for law in federal_laws:
            cleaned_law = re.sub(r'^[\d\.\-\•\s]+', '', law).strip()

            if cleaned_law and len(cleaned_law) > 4 and not any(p in cleaned_law.lower() for p in ['punjab', 'sindh', 'balochistan', 'khyber', 'gilgit']):
                if any(keyword in cleaned_law.lower() for keyword in valid_keywords):
                    cleaned_laws.append(cleaned_law)

        cleaned_laws = list(dict.fromkeys(cleaned_laws))

        return cleaned_laws

    except Exception as e:
        print(f"Error extracting laws: {e}")
        return []


def search_law_pdfs(laws):
    results = {}

    output_dir = "women_laws_pdfs"
    os.makedirs(output_dir, exist_ok=True)

    for law in laws:
        print(f"\n🔍 Searching for PDF of: {law}")
        
        search_queries = [
            f"{law} Pakistan official pdf filetype:pdf",
            f"{law} pakistan government gazette filetype:pdf",
            f"{law} text pakistan filetype:pdf",
            f"{law} act pakistan filetype:pdf",
            f"pakistan {law} official document filetype:pdf"
        ]

        pdf_urls = []
        for query in search_queries:
            try:
                print(f"   ➤ Query: {query}")
                for url in search(query, num=3, stop=3, pause=2):
                    if url.lower().endswith(".pdf") and url not in pdf_urls:
                        pdf_urls.append(url)
                
                if pdf_urls:
                    print(f" Found {len(pdf_urls)} PDF link(s).")
                    break 
                time.sleep(3)

            except Exception as e:
                print(f" Error during search: {e}")
                time.sleep(5)

        if pdf_urls:
            success = False
            for pdf_url in pdf_urls:
                try:
                    file_name = re.sub(r"[^\w\s-]", "", law)
                    file_name = re.sub(r"\s+", "_", file_name)[:50] + ".pdf"
                    file_path = os.path.join(output_dir, file_name)

                    print(f"Downloading: {pdf_url}")
                    response = requests.get(pdf_url, stream=True, timeout=30)
                    response.raise_for_status()

                    if "application/pdf" in response.headers.get("Content-Type", ""):
                        with open(file_path, "wb") as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        print(f"   📥 Saved to: {file_path}")
                        results[law] = {
                            "status": "Success",
                            "url": pdf_url,
                            "path": file_path
                        }
                        success = True
                        break
                    else:
                        print(f"Not a valid PDF file.")

                except Exception as e:
                    print(f"Failed to download from {pdf_url}: {e}")

            if not success:
                results[law] = {
                    "status": "Found URLs but download failed",
                    "urls": pdf_urls
                }
        else:
            print(f"   ❌ No PDF found for '{law}'")
            results[law] = {
                "status": "No PDF found"
            }
        time.sleep(5) 

    return results

# Function to verify PDFs and check their content
def verify_pdfs(results):
    keywords = ['law', 'bill', 'amendment', 'act', 'ordinance', 'rights', 'ord', 'protection']
    
    print("Total downloaded PDFs to verify:", len(results))

    for law, result in results.items():
        if result['status'] == 'Success' and 'path' in result:
            pdf_path = result['path']
            filename = os.path.basename(pdf_path).lower()

            if not any(kw in filename for kw in keywords):
                print(f"File '{filename}' doesn't match naming keywords. Deleting...")
                try:
                    os.remove(pdf_path)
                    result['verification'] = {
                        'valid_pdf': False,
                        'reason': 'Filename did not contain law-related keyword, deleted.'
                    }
                except Exception as e:
                    print(f"⚠️ Error deleting file '{pdf_path}': {e}")
                    result['verification'] = {
                        'valid_pdf': False,
                        'error': str(e)
                    }
                continue

            try:
                with open(pdf_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    num_pages = len(pdf_reader.pages)
                    first_page_text = pdf_reader.pages[0].extract_text() or ""

                    law_keywords = [word.lower() for word in law.split() if len(word) > 3]
                    matches = sum(1 for keyword in law_keywords if keyword in first_page_text.lower())
                    relevance_score = matches / len(law_keywords) if law_keywords else 0

                    result['verification'] = {
                        'valid_pdf': True,
                        'pages': num_pages,
                        'relevance_score': relevance_score,
                        'likely_match': relevance_score > 0.3
                    }

                    print(f"Verified PDF for '{law}': {num_pages} pages, relevance score: {relevance_score:.2f}")

            except Exception as e:
                print(f" Error verifying PDF for '{law}': {e}")
                result['verification'] = {
                    'valid_pdf': False,
                    'error': str(e)
                }
    print("Results after verification:", len(results))
    return results

# Function to analyze a specific PDF
def analyze_pdf(pdf_path, pages_to_analyze=3):
    try:
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            num_pages = len(pdf_reader.pages)
            
            print(f"PDF has {num_pages} pages")
            
            pages_to_read = min(pages_to_analyze, num_pages)
            for i in range(pages_to_read):
                page_text = pdf_reader.pages[i].extract_text()
                
                preview = page_text[:500] + "..." if len(page_text) > 500 else page_text
                print(f"\nPage {i+1} preview:\n{preview}")
    except Exception as e:
        print(f"Error analyzing PDF: {e}")

# Function to try direct DOM exploration as a last resort
def explore_dom_for_laws(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def extract_nested_text(element, level=0):
        laws = []
        if element.name in ['p', 'div', 'li']:
            text = element.get_text(separator=' ', strip=True)
            if any(k in text for k in ['Act', 'Ordinance', 'Law', 'Bill', 'Amendment']) and len(text) > 15:
                laws.append(('  ' * level) + text)

        for child in element.find_all(['ul', 'ol', 'li', 'div'], recursive=False):
            laws.extend(extract_nested_text(child, level + 1))

        return laws

    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        potential_laws = []

        for container in soup.find_all(['div', 'p', 'ul', 'ol']):
            potential_laws.extend(extract_nested_text(container))

        cleaned_laws = []
        valid_keywords = ['act', 'law', 'bill', 'ordinance', 'amendment']

        for law in potential_laws:
            cleaned_law = re.sub(r'^[\d\.\-\•\s]+', '', law).strip()

            if cleaned_law and len(cleaned_law) > 4 and not any(p in cleaned_law.lower() for p in ['punjab', 'sindh', 'balochistan', 'khyber', 'gilgit', 'sind']):
                if any(keyword in cleaned_law.lower() for keyword in valid_keywords):
                    cleaned_laws.append(cleaned_law)

        cleaned_laws = list(dict.fromkeys(cleaned_laws))

        return cleaned_laws

    except Exception as e:
        print(f"Error in DOM exploration: {e}")
        return []


def main():
    url = "https://ncsw.gov.pk/Detail/OWYxM2U1MWYtZDZhNS00YTA3LWIwOTItNzBhMmZlMDIxNzlj"
    
    print("\nExtracting federal laws from the website...")
    federal_laws = extract_federal_laws(url)
    
    if not federal_laws:
        print("\nPrimary extraction method failed. Trying alternative approach...")
        federal_laws = explore_dom_for_laws(url)
    
    if not federal_laws:
        print("\nCould not extract any laws from the webpage. Please check the webpage structure manually.")
        print("You can examine the saved 'webpage_content.html' file to identify the laws.")
        return
    
    print("\nFound the following federal laws:")
    for i, law in enumerate(federal_laws, 1):
        print(f"{i}. {law}")
    
    print("\nNow searching for PDF versions of these laws...")
    results = search_law_pdfs(federal_laws)
    
    print("\nVerifying downloaded PDFs...")
    try:
        verified_results = verify_pdfs(results)
    except Exception as e:
        print(f"Error during PDF verification: {e}")
        verified_results = results
    
    print("\nSummary of results:")
    for law, result in verified_results.items():
        print(f"\n- {law}")
        print(f"  Status: {result['status']}")
        if 'url' in result:
            print(f"  URL: {result['url']}")
        if 'path' in result:
            print(f"  Saved to: {result['path']}")
        if 'verification' in result:
            v = result['verification']
            if v.get('valid_pdf', False):
                print(f"  Pages: {v['pages']}")
                print(f"  Relevance score: {v['relevance_score']:.2f}")
                print(f"  Likely match: {'Yes' if v.get('likely_match', False) else 'No'}")

if __name__ == "__main__":
    main()
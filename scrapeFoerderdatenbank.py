import random
import time
import os
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Base URL for the Förderdatenbank with query parameters
BASE_URL = "https://www.foerderdatenbank.de/SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html"

# Custom headers to mimic a browser
HEADERS = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"},
]

def fetch_page(url, retries=5):
    """Fetches a specific page of Förderungen results with retries."""
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=random.choice(HEADERS), timeout=10)
            if response.status_code == 200:
                print(f"Successfully fetched: {url}")
                return response.text
            else:
                print(f"Failed to fetch page (status: {response.status_code}). Retrying...")
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}. Retrying ({attempt + 1}/{retries})...")
        time.sleep(2 ** attempt + random.random())  # Exponential backoff
    print(f"Failed to fetch {url} after {retries} retries.")
    return None

def parse_program_details(program_url):
    """Fetches and parses the details of a specific program."""
    html_content = fetch_page(program_url)
    if not html_content:
        return {"Error": f"Failed to fetch {program_url}"}

    soup = BeautifulSoup(html_content, 'html.parser')
    details = {}

    # Extract title
    details['Title (Details Page)'] = soup.find("h1", class_="title").text.strip() if soup.find("h1", class_="title") else "No Title"

    # Funding details
    for dl in soup.find_all("dl", class_="grid-modul--two-elements document-info-fundingprogram"):
        for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
            details[dt.text.strip().rstrip(":")] = dd.text.strip()

    # Extract "Weiterführende Links"
    link_names, link_urls = [], []
    for link in soup.select("dd a.link-external"):
        link_names.append(link.text.strip())
        link_urls.append(link['href'])
    details['Weiterführende Link Names'] = "; ".join(link_names) or "No Links"
    details['Weiterführende Link URLs'] = "; ".join(link_urls) or "No Links"

    # Extract dynamic tabs (including hyperlinks)
    tabs = {}
    current_tab = None

    for element in soup.find_all(["h2", "div"]):
        # Detect headings (tabs)
        if element.name == "h2" and element.get("class") and "horizontal--tab-opener" in element["class"]:
            current_tab = element.get_text(strip=True)  # Heading text as key
            tabs[current_tab] = {"content": [], "hyperlink_labels": [],
                                 "hyperlink_urls": []}  # Initialize content for this tab
        # Extract content and hyperlinks for the current tab
        elif current_tab and element.name == "div" and "rich--text" in element.get("class", []):
            # Extract text content
            tabs[current_tab]["content"].append(element.get_text(separator=" ", strip=True))
            # Extract hyperlinks
            for link in element.find_all("a", href=True):
                tabs[current_tab]["hyperlink_labels"].append(link.text.strip())
                tabs[current_tab]["hyperlink_urls"].append(link['href'])

    # If no tabs were found, directly grab all "rich--text" content
    if not tabs:
        general_content = []
        general_hyperlinks = {"labels": [], "urls": []}
        for div in soup.find_all("div", class_="rich--text"):
            general_content.append(div.get_text(separator=" ", strip=True))
            for link in div.find_all("a", href=True):
                general_hyperlinks["labels"].append(link.text.strip())
                general_hyperlinks["urls"].append(link['href'])

        tabs["General Content"] = {
            "content": " ".join(general_content) if general_content else "Nicht vorhanden",
            "hyperlink_labels": "; ".join(general_hyperlinks["labels"]),
            "hyperlink_urls": "; ".join(general_hyperlinks["urls"]),
        }

    # Combine tab contents into the final details dictionary
    for tab_name, tab_data in tabs.items():
        details[tab_name + " Content"] = " ".join(tab_data["content"]) if isinstance(tab_data["content"], list) else \
        tab_data["content"]
        details[tab_name + " Hyperlink Labels"] = "; ".join(tab_data["hyperlink_labels"]) if tab_data[
            "hyperlink_labels"] else "No Links"
        details[tab_name + " Hyperlink URLs"] = "; ".join(tab_data["hyperlink_urls"]) if tab_data[
            "hyperlink_urls"] else "No Links"



    return details

def parse_results(html_content):
    """Parses the HTML content and extracts funding program details."""
    soup = BeautifulSoup(html_content, 'html.parser')
    programs = []

    for card in soup.find_all("div", class_="card card--horizontal card--fundingprogram"):
        title = card.find("span", class_="link--label").text.strip() if card.find("span", class_="link--label") else "No Title"
        link = card.find("a", href=True)['href'] if card.find("a", href=True) else "No Link"
        full_link = f"https://www.foerderdatenbank.de/{link}"

        funding_targets = funding_purpose = "Nicht angegeben"
        for dl in card.find_all("dl", class_="grid-modul--two-elements document-info-fundingprogram"):
            for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
                if "Wer wird gefördert?" in dt.text:
                    funding_targets = dd.text.strip()
                elif "Was wird gefördert?" in dt.text:
                    funding_purpose = dd.text.strip()

        details = parse_program_details(full_link)
        program_data = {
            "Title": title,
            "Link": full_link,
            "Who is funded": funding_targets,
            "What is funded": funding_purpose,
            **details
        }
        programs.append(program_data)

    next_page_tag = soup.find("a", class_="forward button", string="weiter")
    next_page_link = f"https://www.foerderdatenbank.de/{next_page_tag['href']}" if next_page_tag else None
    return programs, next_page_link

def scrape_all_pages(max_pages=5, resume_file="foerderungen_list.csv"):
    """Scrapes all pages and saves progress incrementally."""
    all_programs = []
    last_page = 1

    if os.path.exists(resume_file):
        print(f"Resuming from {resume_file}...")
        df = pd.read_csv(resume_file)
        all_programs = df.to_dict(orient='records')
        last_page = (len(df) // 10) + 1  # Estimate page number

    current_page_url = BASE_URL + "?resourceId=86eabea6-8d08-40e7-a272-b337e51c6613&filterCategories=FundingProgram&submit=Suchen&templateQueryString=&pageLocale=de&sortOrder=dateOfIssue_dt+asc"

    for page in range(last_page, max_pages + 1):
        time.sleep(random.randint(5, 15))  # Randomized delays
        print(f"Fetching page {page}...")
        html_content = fetch_page(current_page_url)
        if not html_content:
            break

        programs, next_page_link = parse_results(html_content)
        all_programs.extend(programs)

        df = pd.DataFrame(all_programs)
        df.to_csv(resume_file, index=False, encoding="utf-8")
        print(f"Saved progress to {resume_file}")

        if not next_page_link:
            print("No more pages found.")
            break
        current_page_url = next_page_link

    print("Scraping complete.")
    return all_programs

# Main execution
if __name__ == "__main__":
    max_pages_to_scrape = 250
    scrape_all_pages(max_pages=max_pages_to_scrape)

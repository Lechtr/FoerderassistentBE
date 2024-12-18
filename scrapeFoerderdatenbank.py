import random
import time

import requests
from bs4 import BeautifulSoup
import pandas as pd

# Base URL for the Förderdatenbank with query parameters
BASE_URL = "https://www.foerderdatenbank.de/SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html"

# Custom headers to mimic a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def fetch_page(url):
    """Fetches a specific page of Förderungen results."""
    response = requests.get(url, headers=HEADERS)
    print(f"Fetching: {response.url}")
    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to fetch page. Status code: {response.status_code}")
        return None


def parse_results(html_content):
    """Parses the HTML content and extracts funding program details."""
    soup = BeautifulSoup(html_content, 'html.parser')
    programs = []

    # Find all cards with funding program details
    for card in soup.find_all("div", class_="card card--horizontal card--fundingprogram"):
        title = card.find("span", class_="link--label").text.strip() if card.find("span",
                                                                                  class_="link--label") else "No Title"
        link = card.find("a", href=True)['href'] if card.find("a", href=True) else "No Link"
        full_link = f"https://www.foerderdatenbank.de/{link}"

        # Extract 'Wer wird gefördert?' and 'Was wird gefördert?'
        funding_targets = "Nicht angegeben"
        funding_purpose = "Nicht angegeben"
        dt_dd_pairs = card.find_all("dl", class_="grid-modul--two-elements document-info-fundingprogram")

        for dl in dt_dd_pairs:
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds):
                if "Wer wird gefördert?" in dt.text:
                    funding_targets = dd.text.strip()
                elif "Was wird gefördert?" in dt.text:
                    funding_purpose = dd.text.strip()

        programs.append({
            "Title": title,
            "Link": full_link,
            "Who is funded": funding_targets,
            "What is funded": funding_purpose
        })


    # Find "weiter" link for the next page
    next_page_tag = soup.find("a", class_="forward button", string="weiter")
    if next_page_tag and "href" in next_page_tag.attrs:
        next_page_link = "https://www.foerderdatenbank.de/" + next_page_tag['href']
    else:
        next_page_link = None
        print("No 'weiter' button found.")


    return programs, next_page_link

href="SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html?gtp=%2526816beae2-d57e-4bdc-b55d-392bc1e17027_list%253D2&amp;submit=Suchen&amp;resourceId=86eabea6-8d08-40e7-a272-b337e51c6613&amp;filterCategories=FundingProgram&amp;pageLocale=de"
href="SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html?gtp=%2526816beae2-d57e-4bdc-b55d-392bc1e17027_list%253D3&amp;submit=Suchen&amp;resourceId=86eabea6-8d08-40e7-a272-b337e51c6613&amp;filterCategories=FundingProgram&amp;pageLocale=de"

def scrape_all_pages(max_pages=5):
    """Scrapes all pages up to the given limit."""
    all_programs = []
    current_page_url = BASE_URL + "?resourceId=86eabea6-8d08-40e7-a272-b337e51c6613&filterCategories=FundingProgram&submit=Suchen&templateQueryString=&pageLocale=de&sortOrder=dateOfIssue_dt+asc"



    for page in range(1, max_pages + 1):
        # wait a random time to prevent blocking of the scraped site
        time.sleep(random.randint(1, 10))
        print(f"Fetching page {page}...")
        html_content = fetch_page(current_page_url)
        if not html_content:
            break

        programs, next_page_link = parse_results(html_content)
        all_programs.extend(programs)

        if not next_page_link:
            break
        current_page_url = next_page_link

        # Stop if no more results exist (implement a check based on the site's behavior)
    return all_programs

# Main script execution
if __name__ == "__main__":
    max_pages_to_scrape = 10  # Adjust as needed
    results = scrape_all_pages(max_pages=max_pages_to_scrape)

    # Save results to CSV
    df = pd.DataFrame(results)
    df.to_csv("foerderungen_list.csv", index=False, encoding="utf-8")
    print("Data saved to foerderungen_list.csv")

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



def parse_program_details( program_url ):
    """Fetches and parses the details of a specific program."""
    html_content = fetch_page(program_url)

    soup = BeautifulSoup(html_content, 'html.parser')
    details = {}

    # Extract relevant fields from detailed page
    details['Title (Details Page)'] = soup.find("h1", class_="title").text.strip() if soup.find("h1",
                                                                                                class_="title") else "No Title"

    # Funding details
    for dl in soup.find_all("dl", class_="grid-modul--two-elements document-info-fundingprogram"):
        for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
            details[dt.text.strip().rstrip(":")] = dd.text.strip()


    # Extract "Weiterführende Links" with actual hyperlinks
    link_names = []
    link_urls = []
    for link in soup.select("dd a.link-external"):
        link_names.append(link.text.strip())
        link_urls.append(link['href'])

    # Add link names and URLs as separate columns
    details['Weiterführende Link Names'] = "; ".join(link_names) if link_names else "No Links"
    details['Weiterführende Link URLs'] = "; ".join(link_urls) if link_urls else "No Links"




    # Dynamically extract all tabs and their content
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

        # Fetch details from the specific program page
        details = parse_program_details(full_link)

        program_data = {
            "Title": title,
            "Link": full_link,
            "Who is funded": funding_targets,
            "What is funded": funding_purpose
        }

        program_data.update(details)  # Merge general and detailed data
        programs.append(program_data)


    # Find "weiter" link for the next page
    next_page_tag = soup.find("a", class_="forward button", string="weiter")
    if next_page_tag and "href" in next_page_tag.attrs:
        next_page_link = "https://www.foerderdatenbank.de/" + next_page_tag['href']
    else:
        next_page_link = None
        print("No 'weiter' button found.")


    return programs, next_page_link



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

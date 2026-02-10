import os
import requests
from bs4 import BeautifulSoup
import re
import datetime
import time # Added for safety

# ==========================================
# CONFIGURATION
# ==========================================
USER_ID = "_4mmNBMAAAAJ" 
TARGET_YEAR = "2026"     
HTML_FILE = "publications.html"
OUTPUT_FILE = "publications_updated.html"
API_KEY = os.environ.get("SERP_API_KEY")

VENUE_ACRONYMS = {
    "Solid-State Circuits": "JSSC",
    "Biomedical Engineering": "TBME",
    "Computer-Aided Design": "TCAD",
    "Internet of Things": "IoTJ",
    "Microwave Theory": "TMTT",
    "Circuits and Systems I": "TCAS-I",
    "Circuits and Systems II": "TCAS-II",
    "Nature Electronics": "NatE",
    "Nature Communications": "NatComm",
    "Scientific Reports": "NatSR",
    "Open Journal of the Solid-State": "OJ-SSCS",
    "Antennas and Propagation": "ToAP",
    "Communications Engineering": "NatCE",
    "Very Large Scale Integration": "TVLSI",
    "ISSCC": "ISSCC",
    "CICC": "CICC",
    "EMBC": "EMBC",
    "BioCAS": "BioCAS",
    "IMS": "IMS",
    "Symposium on VLSI": "VLSI",
    "Design, Automation": "DATE",
    "Body Sensor Networks": "BSN"
}

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_real_publisher_link(scholar_url):
    """
    Visits the Google Scholar internal citation page to find the 
    Publisher URL (Title Link) or PDF Link.
    """
    if not scholar_url: return None
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        # We perform a lightweight request to the scholar detail page
        response = requests.get(scholar_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return scholar_url # Fallback to scholar link if fail
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. Try to find the Main Article Link (The Title Link)
        title_link = soup.find("a", class_="gsc_oci_title_link")
        if title_link and title_link.get("href"):
            return title_link.get("href")
            
        # 2. If not found, try finding a PDF link on the right side
        ggi = soup.find("div", class_="gsc_oci_title_ggi")
        if ggi:
            pdf_link = ggi.find("a")
            if pdf_link and pdf_link.get("href"):
                return pdf_link.get("href")
                
        # 3. If neither found, return the original scholar link
        return scholar_url
        
    except Exception as e:
        print(f"Warning: Could not resolve deep link: {e}")
        return scholar_url

def fetch_papers_via_api():
    """Fetches papers using SerpApi and then resolves deep links."""
    if not API_KEY:
        print("Error: SERP_API_KEY not found in secrets.")
        return []

    print(f"Fetching papers for User {USER_ID} via SerpApi...")
    
    params = {
        "engine": "google_scholar_author",
        "author_id": USER_ID,
        "api_key": API_KEY,
        "sort": "pubdate",
        "num": 20 
    }
    
    try:
        response = requests.get("https://serpapi.com/search", params=params)
        response.raise_for_status()
        data = response.json()
        
        articles = data.get("articles", [])
        valid_papers = []
        
        for art in articles:
            year = art.get("year", "Unknown")
            
            # Filter by Target Year
            if TARGET_YEAR != "ALL" and str(year) != str(TARGET_YEAR):
                continue
                
            venue_raw = art.get("publication", "") 
            venue_clean = venue_raw.strip()
            scholar_link = art.get("link")
            
            # --- THE FIX: RESOLVE DEEP LINK ---
            print(f"Resolving link for: {art.get('title')[:30]}...")
            final_link = get_real_publisher_link(scholar_link)
            time.sleep(1) # Polite pause to avoid rate limiting on the scraper part
            # ----------------------------------

            paper = {
                "title": art.get("title"),
                "authors": art.get("authors", "Unknown"), 
                "venue": venue_clean,
                "year": str(year),
                "link": final_link, # Updated to use the resolved link
                "category": "Conference Papers" if any(x in venue_clean.lower() for x in ["conf", "proc", "symp", "meeting"]) else "Journal Papers"
            }
            valid_papers.append(paper)
            
        return valid_papers

    except Exception as e:
        print(f"API Request Failed: {e}")
        return []

def format_authors(author_string):
    if not author_string or author_string == "Unknown": return author_string
    names = author_string.split(',')
    formatted = []
    for name in names:
        parts = name.strip().split()
        if len(parts) >= 2:
            formatted.append(f"{parts[0][0]}. {parts[-1]}")
        else:
            formatted.append(name)
    return ", ".join(formatted)

def extract_acronym(venue_name):
    if not venue_name: return None
    for key, acro in VENUE_ACRONYMS.items():
        if key.lower() in venue_name.lower(): return acro
    match = re.search(r'\((?P<found>[A-Z0-9-]{2,})\)$', venue_name.strip())
    if match: return match.group('found')
    return None

def parse_existing_html(html_file):
    try:
        with open(html_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
    except FileNotFoundError:
        return {"journals": [], "conferences": []}, None, {"J": 0, "C": 0}

    parsed_papers = {"journals": [], "conferences": []}
    max_ids = {"J": 0, "C": 0}
    
    for cat_id in ["journals", "conferences"]:
        container = soup.find("div", id=cat_id)
        if not container: continue
        prefix = "J" if cat_id == "journals" else "C"
        
        for div in container.find_all("div", class_="filterDiv"):
            year = div.get('data-year', "Unknown")
            for p in div.find_all('p'):
                text = p.get_text(" ", strip=True)
                id_match = re.match(rf'^\s*({prefix})(\d+)\.', text)
                if id_match:
                    num = int(id_match.group(2))
                    if num > max_ids[prefix]: max_ids[prefix] = num
                
                title_match = re.search(r'["“]([^"”]+)["”]', text)
                title = title_match.group(1) if title_match else ""
                content_cleaned = re.sub(rf'^\s*{prefix}\d+\.\s*', '', p.decode_contents()).strip()
                
                parsed_papers[cat_id].append({
                    "title": title, 
                    "year": year, 
                    "raw_content": content_cleaned, 
                    "is_new": False
                })
    return parsed_papers, soup, max_ids

def reconstruct_html(soup, all_data, current_max_ids):
    for cat_id in ["journals", "conferences"]:
        prefix = "J" if cat_id == "journals" else "C"
        new_papers = [p for p in all_data[cat_id] if p.get('is_new')]
        old_papers = [p for p in all_data[cat_id] if not p.get('is_new')]
        
        total_new = len(new_papers)
        for i, paper in enumerate(new_papers):
            paper['new_id'] = f"{prefix}{current_max_ids[prefix] + total_new - i}"
        
        final_list = new_papers + old_papers
        container = soup.find("div", id=cat_id)
        if not container: continue
        for div in container.find_all("div", class_="filterDiv"): div.decompose()
        
        papers_by_year = {}
        for p in final_list:
            y = p['year'] if p['year'] else "Unknown"
            if y not in papers_by_year: papers_by_year[y] = []
            papers_by_year[y].append(p)
            
        sorted_years = sorted(papers_by_year.keys(), key=lambda x: int(x) if x.isdigit() else 0, reverse=True)
        insert_marker = container.find("div", class_="logo-strip") or container.find("div", class_="section-header")
        
        for year in sorted_years:
            new_div = soup.new_tag("div", attrs={"class": "filterDiv", "data-year": year})
            h2 = soup.new_tag("h2", attrs={"class": "accent"})
            h2.string = year
            new_div.append(h2)
            
            for p in papers_by_year[year]:
                if p.get('is_new'):
                    venue_text = p['venue']
                    acro = extract_acronym(venue_text)
                    if acro:
                        venue_text = venue_text.replace(f"({acro})", "").strip()
                        acro_html = f'<b>({acro})</b>'
                    else:
                        acro_html = ""
                        
                    link = p.get('link', '#')
                    fmt_auth = format_authors(p['authors'])
                    
                    content = f'{p["new_id"]}. {fmt_auth}, "{p["title"]}", in {venue_text} {acro_html} - Jan {year} [ <a href="{link}" target="_blank" class="fa fa-file-pdf-o" style="color:red"></a> <a href="{link}" target="_blank"> Paper Link</a> ]'
                else:
                    content = f"{prefix}{len(old_papers) - old_papers.index(p)}. {p['raw_content']}"
                
                p_tag_soup = BeautifulSoup(f"<p>{content}</p>", "html.parser")
                if p_tag_soup.p: new_div.append(p_tag_soup.p)
            
            insert_marker.insert_after(new_div)
            insert_marker = new_div
            
    return soup

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    parsed_data, soup, max_ids = parse_existing_html(HTML_FILE)
    if not soup:
        print("Error: Could not parse HTML file.")
        exit(1)

    api_papers = fetch_papers_via_api()
    
    missing_papers = []
    existing_titles = [p['title'].lower().strip() for p in parsed_data['journals'] + parsed_data['conferences']]
    
    for new_p in api_papers:
        is_duplicate = False
        new_title = new_p['title'].lower().strip()
        if new_title in existing_titles:
            is_duplicate = True
        
        if not is_duplicate:
            missing_papers.append(new_p)

    report_lines = []
    
    if not missing_papers:
        msg = "No new papers found."
        print(msg)
        report_lines.append(msg)
    else:
        print(f"Found {len(missing_papers)} new papers.")
        
        for p in missing_papers:
            p['is_new'] = True
            key = 'conferences' if p['category'] == "Conference Papers" else 'journals'
            parsed_data[key].append(p)
            
        updated_soup = reconstruct_html(soup, parsed_data, max_ids)
        
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(updated_soup.prettify())
            
        report_lines.append("="*60)
        report_lines.append(f" AUTO-UPDATE REPORT: {len(missing_papers)} NEW ENTRIES")
        report_lines.append(f" Target Year: {TARGET_YEAR}")
        report_lines.append("="*60)

        for cat in ["journals", "conferences"]:
            new_entries = [p for p in parsed_data[cat] if p.get('is_new')]
            if new_entries:
                report_lines.append(f"\n--- {cat.upper()} ---")
                for p in new_entries:
                    acro = extract_acronym(p['venue'])
                    acro_disp = acro if acro else "None Detected"
                    link = p.get('link', 'No Link')
                    
                    report_lines.append(f"ID:       {p['new_id']}")
                    report_lines.append(f"Title:    {p['title']}")
                    report_lines.append(f"Venue:    {p['venue']}")
                    report_lines.append(f"Acronym: {acro_disp}")
                    report_lines.append(f"Link:     {link}")
                    report_lines.append("-" * 40)

    with open("report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

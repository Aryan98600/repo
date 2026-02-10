import os
import requests
from bs4 import BeautifulSoup
import re
import datetime

# ==========================================
# CONFIGURATION
# ==========================================
USER_ID = "_4mmNBMAAAAJ"  # Your Google Scholar ID
TARGET_YEAR = "2026"      # Year to scan for
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
# FUNCTIONS
# ==========================================

def fetch_papers_via_api():
    """Fetches papers using SerpApi to avoid Google blocks."""
    if not API_KEY:
        print("Error: SERP_API_KEY not found in secrets.")
        return []

    print(f"Fetching papers for User {USER_ID} via SerpApi...")
    
    params = {
        "engine": "google_scholar",
        "author_id": USER_ID,
        "api_key": API_KEY,
        "sort": "pubdate", # Sort by newest
        "num": 20          # Check last 20 papers
    }
    
    try:
        response = requests.get("https://serpapi.com/search", params=params)
        response.raise_for_status()
        data = response.json()
        
        articles = data.get("articles", [])
        valid_papers = []
        
        for art in articles:
            # Safe extraction of year
            pub_info = art.get("publication_info", {})
            summary = pub_info.get("summary", "")
            
            # Extract year from summary string (e.g. "S Sen... - 2025 - publisher")
            year_match = re.search(r'\b(20\d{2})\b', summary)
            year = year_match.group(1) if year_match else "Unknown"
            
            # Filter by Target Year
            if TARGET_YEAR != "ALL" and year != TARGET_YEAR:
                continue
                
            # Formatting Data
            venue_raw = summary.split('-')[1].strip() if '-' in summary else ""
            # Sometimes venue is mixed with year, clean it up roughly
            venue_clean = re.sub(r'\b20\d{2}\b', '', venue_raw).strip()
            
            paper = {
                "title": art.get("title"),
                "authors": pub_info.get("authors", "Unknown"), # SerpApi gives authors list
                "venue": venue_clean,
                "year": year,
                "link": art.get("link"), # Direct PDF or publisher link
                "category": "Conference Papers" if any(x in venue_clean.lower() for x in ["conf", "proc", "symp", "meeting"]) else "Journal Papers"
            }
            valid_papers.append(paper)
            
        return valid_papers

    except Exception as e:
        print(f"API Request Failed: {e}")
        return []

def format_authors(author_string):
    # SerpApi sometimes returns a list, sometimes a string. Handle both.
    if isinstance(author_string, list):
        names = [n.get("name", "") for n in author_string]
    else:
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
    # 1. Check Manual Dictionary
    for key, acro in VENUE_ACRONYMS.items():
        if key.lower() in venue_name.lower(): return acro
    # 2. Check Parentheses Regex
    match = re.search(r'\((?P<found>[A-Z0-9-]{2,})\)$', venue_name.strip())
    if match: return match.group('found')
    return None

def parse_existing_html(html_file):
    """Parses existing HTML to find current Max IDs and Titles."""
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
                
                # Extract ID to find max
                id_match = re.match(rf'^\s*({prefix})(\d+)\.', text)
                if id_match:
                    num = int(id_match.group(2))
                    if num > max_ids[prefix]: max_ids[prefix] = num
                
                # Extract Title for duplicate checking
                title_match = re.search(r'["“]([^"”]+)["”]', text)
                title = title_match.group(1) if title_match else ""
                
                # Clean content for reconstruction
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
        
        # Assign New IDs
        total_new = len(new_papers)
        for i, paper in enumerate(new_papers):
            paper['new_id'] = f"{prefix}{current_max_ids[prefix] + total_new - i}"
        
        # Merge and Sort
        final_list = new_papers + old_papers
        
        # Clear container
        container = soup.find("div", id=cat_id)
        if not container: continue
        for div in container.find_all("div", class_="filterDiv"): div.decompose()
        
        # Group by Year
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
                    # --- NEW FORMATTING LOGIC ---
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
                    # Restore ID
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
    # 1. Fetch Existing Data
    parsed_data, soup, max_ids = parse_existing_html(HTML_FILE)
    if not soup:
        print("Error: Could not parse HTML file.")
        exit(1)

    # 2. Fetch New Papers via API
    api_papers = fetch_papers_via_api()
    
    # 3. Check for Duplicates (Fuzzy Match or Exact Title)
    missing_papers = []
    existing_titles = [p['title'].lower().strip() for p in parsed_data['journals'] + parsed_data['conferences']]
    
    for new_p in api_papers:
        is_duplicate = False
        new_title = new_p['title'].lower().strip()
        
        # Exact match check
        if new_title in existing_titles:
            is_duplicate = True
        
        if not is_duplicate:
            missing_papers.append(new_p)

    # 4. Generate Report & Update
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
            
        # Report Generation
        report_lines.append(f"UPDATE REPORT ({datetime.date.today()})")
        report_lines.append(f"New Papers Added: {len(missing_papers)}")
        report_lines.append("-" * 30)
        
        for p in missing_papers:
            report_lines.append(f"Title: {p['title']}")
            report_lines.append(f"Venue: {p['venue']}")
            report_lines.append(f"Link:  {p['link']}")
            report_lines.append("-" * 30)

    # 5. Write Report
    with open("report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

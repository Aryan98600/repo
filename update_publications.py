import requests
from bs4 import BeautifulSoup
import re
import time
from rapidfuzz import fuzz

# ==========================================
# CONFIGURATION
# ==========================================
USER_ID = "_4mmNBMAAAAJ"        # Google Scholar ID
TARGET_YEAR = "2026"            # Enter "2025" or "ALL"
HTML_FILE = "publications.html"
OUTPUT_FILE = "publications_updated.html"

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

def get_soup(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        time.sleep(1.5) 
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"Request failed: {e}")
        return None

def format_authors(author_string):
    if not author_string or author_string == "Unknown":
        return author_string
    formatted_list = []
    names = [n.strip() for n in author_string.split(',')]
    for name in names:
        parts = name.split()
        if len(parts) >= 2:
            formatted_list.append(f"{parts[0][0]}. {parts[-1]}")
        else:
            formatted_list.append(name)
    return ", ".join(formatted_list)

def classify_paper(venue):
    v = venue.lower()
    if re.search(r'\b(patent|pat\.|app\.|us\s?\d|wo\s?\d)\b', v): return "Patents"
    if re.search(r'\b(arxiv|biorxiv|medrxiv|ssrn|tech\.\s?rep)\b', v): return "Journal Papers"
    conf_keywords = ["conference", "symposium", "proceeding", "proc.", "workshop", "digest", "meeting", "congress", "isscc", "dac", "cicc", "embc", "vlsi", "iscas", "biocas", "ims", "date", "bsn"]
    if any(k in v for k in conf_keywords): return "Conference Papers"
    return "Journal Papers"

def extract_acronym(venue_name):
    if not venue_name: return None
    for key, acro in VENUE_ACRONYMS.items():
        if key.lower() in venue_name.lower(): return acro
    return None

def fetch_scholar_data(user_id, target_year):
    all_papers = []
    cstart = 0
    pagesize = 100
    print(f"Scanning Google Scholar for User {user_id}...")
    while True:
        url = f"https://scholar.google.co.in/citations?user={user_id}&hl=en&view_op=list_works&sortby=pubdate&cstart={cstart}&pagesize={pagesize}"
        soup = get_soup(url)
        if not soup: break
        rows = soup.find_all('tr', class_='gsc_a_tr')
        if not rows: break
        for row in rows:
            title_tag = row.find('a', class_='gsc_a_at')
            title = title_tag.text
            details_link = "https://scholar.google.co.in" + title_tag['href']
            gray_divs = row.find_all('div', class_='gs_gray')
            authors_truncated = gray_divs[0].text if len(gray_divs) > 0 else "Unknown"
            venue = gray_divs[1].text if len(gray_divs) > 1 else ""
            year_span = row.find('span', class_='gsc_a_h')
            year = year_span.text.strip() if year_span else ""
            
            if target_year != "ALL":
                if str(target_year) not in year and str(target_year) not in title: continue
            
            venue_clean = venue.split(',')[0].strip()
            cat = classify_paper(venue_clean)
            if cat in ["Patents", "Book Chapters"]: continue

            all_papers.append({
                "title": title, "authors": authors_truncated, "venue": venue_clean,
                "year": year, "details_url": details_link, "category": cat
            })
        if len(rows) < pagesize: break
        cstart += pagesize
    return all_papers

def get_full_paper_details(paper_url):
    print(f"   --> Fetching full details from: {paper_url}...")
    soup = get_soup(paper_url)
    if not soup: return None
    full_data = {}
    fields = soup.find_all("div", class_="gsc_oci_field")
    values = soup.find_all("div", class_="gsc_oci_value")
    for f, v in zip(fields, values):
        if f.text.strip() == "Authors": full_data['authors'] = v.text.strip()
    ggi_div = soup.find("div", class_="gsc_oci_title_ggi")
    if ggi_div and ggi_div.find("a"): full_data['pdf_link'] = ggi_div.find("a")['href']
    title_link_tag = soup.find("a", class_="gsc_oci_title_link")
    if title_link_tag: full_data['article_link'] = title_link_tag['href']
    return full_data

def parse_existing_html_full_structure(html_file):
    with open(html_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
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
                title = title_match.group(1) if title_match else "Unknown"
                content_cleaned = re.sub(rf'^\s*{prefix}\d+\.\s*', '', p.decode_contents()).strip()
                parsed_papers[cat_id].append({"title": title, "year": year, "raw_content": content_cleaned, "is_new": False})
    return parsed_papers, soup, max_ids


def reconstruct_html(soup, all_data, current_max_ids):
    for cat_id in ["journals", "conferences"]:
        prefix = "J" if cat_id == "journals" else "C"
        new_papers = [p for p in all_data[cat_id] if p.get('is_new')]
        old_papers = [p for p in all_data[cat_id] if not p.get('is_new')]
        
        # Incremental ID Assignment
        total_new = len(new_papers)
        for i, paper in enumerate(new_papers):
            paper['new_id'] = f"{prefix}{current_max_ids[prefix] + total_new - i}"
        
        final_list = new_papers + old_papers
        container = soup.find("div", id=cat_id)
        if not container: continue
        for div in container.find_all("div", class_="filterDiv"): div.decompose()
        
        papers_by_year = {}
        for p in final_list:
            y = p['year'] if p['year'] else "2025"
            if y not in papers_by_year: papers_by_year[y] = []
            papers_by_year[y].append(p)
            
        sorted_years = sorted(papers_by_year.keys(), key=lambda x: int(x.split('-')[-1]) if any(c.isdigit() for c in x) else 9999, reverse=True)
        insert_marker = container.find("div", class_="logo-strip") or container.find("div", class_="section-header")
        
        for year in sorted_years:
            new_div = soup.new_tag("div", attrs={"class": "filterDiv", "data-year": year})
            h2 = soup.new_tag("h2", attrs={"class": "accent"})
            h2.string = year
            new_div.append(h2)
            
            for p in papers_by_year[year]:
                if p.get('is_new'):
                    # --- NEW LOGIC START ---
                    venue_text = p['venue']
                    acro = extract_acronym(venue_text) # 1. Check your manual list first

                    # 2. Fallback: Auto-detect (ACRONYM) in parens if not in list
                    if not acro:
                        # Regex looks for (ABC) at the end of the string
                        match = re.search(r'\((?P<found>[A-Z0-9-]{2,})\)$', venue_text.strip())
                        if match:
                            acro = match.group('found')

                    # 3. Construction & Cleanup
                    if acro:
                        # Remove the acronym from the venue text so it doesn't appear twice
                        venue_text = venue_text.replace(f"({acro})", "").strip()
                        acro_html = f'<b>({acro})</b>'
                    else:
                        acro_html = ""
                    # --- NEW LOGIC END ---

                    link = p.get('article_link') or p.get('pdf_link') or p['details_url']
                    
                    # Note: Using venue_text (cleaned) + acro_html (bolded)
                    content = f'{p["new_id"]}. {format_authors(p["authors"])}, "{p["title"]}", in {venue_text} {acro_html} - Jan {year} [ <a href="{link}" target="_blank" class="fa fa-file-pdf-o" style="color:red"></a> <a href="{link}" target="_blank"> Paper Link</a> ]'
                else:
                    content = f"{prefix}{len(old_papers) - old_papers.index(p)}. {p['raw_content']}"
                
                # Safer Append Method
                p_tag_soup = BeautifulSoup(f"<p>{content}</p>", "html.parser")
                if p_tag_soup.p:
                    new_div.append(p_tag_soup.p)
            
            insert_marker.insert_after(new_div)
            insert_marker = new_div
    return soup


# ==========================================
# EXECUTION
# ==========================================


# ... (Keep all your imports and functions exactly as they are) ...

# ==========================================
# HEADLESS EXECUTION (For GitHub Actions)
# ==========================================
if __name__ == "__main__":
    # 1. Fetch Data
    scholar_data = fetch_scholar_data(USER_ID, TARGET_YEAR)
    parsed_data, soup, max_ids = parse_existing_html_full_structure(HTML_FILE)

    # 2. Identify Missing Papers
    missing_papers = []
    all_existing_titles = [p['title'].lower() for p in parsed_data['journals'] + parsed_data['conferences']]
    
    for sp in scholar_data:
        # Check fuzzy match to avoid duplicates
        if not any(fuzz.ratio(sp['title'].lower(), et) > 90 for et in all_existing_titles):
            missing_papers.append(sp)

    # 3. Process Papers (Headless Mode: Always take ALL new papers)
    report_lines = []
    
    if not missing_papers:
        msg = "No new papers found for the target year."
        print(msg)
        report_lines.append(msg)
    else:
        print(f"Found {len(missing_papers)} new papers. Adding ALL automatically...")
        
        # In automation, we skip the input() and just iterate over all missing_papers
        for p in missing_papers:
            details = get_full_paper_details(p['details_url'])
            if details: p.update(details)
            p['is_new'] = True
            key = 'journals' if p['category'] == "Journal Papers" else 'conferences'
            parsed_data[key].append(p)

        # 4. Save Updated HTML
        updated_soup = reconstruct_html(soup, parsed_data, max_ids)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(updated_soup.prettify())
        
        success_msg = f"Success! {len(missing_papers)} added. Updated {OUTPUT_FILE}"
        print(success_msg)
        
        # 5. Generate Report for Email
        report_lines.append("="*60)
        report_lines.append(f" REPORT: {len(missing_papers)} NEW ENTRIES ADDED")
        report_lines.append(f" Target Year: {TARGET_YEAR}")
        report_lines.append("="*60)

        for cat in ["journals", "conferences"]:
            new_entries = [p for p in parsed_data[cat] if p.get('is_new')]
            if new_entries:
                report_lines.append(f"\n[{cat.upper()}]")
                for p in new_entries:
                    raw_auth = p.get('authors', 'Unknown').strip().rstrip(",")
                    fmt_auth = format_authors(raw_auth)
                    report_lines.append(f"{p['new_id']}. {fmt_auth}")
                    report_lines.append(f"    Title: \"{p['title']}...\"")
                    report_lines.append(f"    Venue: {p['venue']}")
                    report_lines.append("-" * 40)

    # 6. Save Report to file (Critical for the Email Step)
    with open("report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

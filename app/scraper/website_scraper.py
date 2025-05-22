"""
Website scraper module for AirdropAgent
"""
import sys
import os
import time
import re
import requests
from urllib.parse import urlparse
from datetime import datetime
import socket
import whois
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Add root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

def get_domain_age(domain):
    """Get domain age in days"""
    try:
        # Remove protocol and path
        if '//' in domain:
            domain = domain.split('//')[1]
        domain = domain.split('/')[0]
        
        w = whois.whois(domain)
        
        # Handle multiple creation dates
        if isinstance(w.creation_date, list):
            creation_date = w.creation_date[0]
        else:
            creation_date = w.creation_date
        
        if creation_date:
            days_old = (datetime.now() - creation_date).days
            return f"{days_old} days ({creation_date.strftime('%Y-%m-%d')})"
        else:
            return "Unknown"
    except Exception as e:
        print(f"Error getting domain age: {e}")
        return "Error retrieving"

def setup_driver(headless=True):
    """Set up Chrome WebDriver"""
    options = Options()
    
    if headless:
        options.add_argument("--headless")
    
    # Common options to make Selenium more stable
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Block images for faster loading
    options.add_argument("--blink-settings=imagesEnabled=false")
    
    # Block notifications
    options.add_argument("--disable-notifications")
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)  # 30 seconds timeout
    return driver

def extract_about_section(soup, url):
    """Extract about section from website"""
    about_sections = []
    
    # Common about section identifiers
    about_keywords = ['about', 'overview', 'introduction', 'project']
    
    # Try to find about section by ID or class
    for keyword in about_keywords:
        # Try id
        about_element = soup.find(id=re.compile(f".*{keyword}.*", re.I))
        if about_element and len(about_element.text.strip()) > 50:
            about_sections.append(about_element.text.strip())
            
        # Try class
        about_elements = soup.find_all(class_=re.compile(f".*{keyword}.*", re.I))
        for element in about_elements:
            if element and len(element.text.strip()) > 50:
                about_sections.append(element.text.strip())
    
    # Look for sections with about heading
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
    for heading in headings:
        if any(keyword in heading.text.lower() for keyword in about_keywords):
            # Get the next siblings until the next heading
            content = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h1', 'h2', 'h3', 'h4']:
                    break
                if sibling.text.strip():
                    content.append(sibling.text.strip())
            if content:
                about_sections.append(' '.join(content))
    
    # If no specific about section found, use meta description
    if not about_sections:
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and 'content' in meta_desc.attrs:
            about_sections.append(meta_desc['content'])
    
    # If still nothing, grab the first paragraphs
    if not about_sections:
        paragraphs = soup.find_all('p')
        relevant_paragraphs = [p.text.strip() for p in paragraphs[:5] if len(p.text.strip()) > 50]
        about_sections.extend(relevant_paragraphs)
    
    # Combine and clean
    about_text = ' '.join(about_sections)
    about_text = re.sub(r'\s+', ' ', about_text).strip()
    
    # Truncate if too long
    if len(about_text) > 1000:
        about_text = about_text[:997] + "..."
    
    return about_text if about_text else f"No about information found on {url}"

def extract_team_info(soup):
    """Extract team information from website"""
    team_sections = []
    
    # Common team section identifiers
    team_keywords = ['team', 'members', 'founders', 'core team', 'our team', 'about us']
    
    # Try to find team section by ID or class
    for keyword in team_keywords:
        # Try id
        team_element = soup.find(id=re.compile(f".*{keyword}.*", re.I))
        if team_element:
            team_sections.append(team_element.text.strip())
            
        # Try class
        team_elements = soup.find_all(class_=re.compile(f".*{keyword}.*", re.I))
        for element in team_elements:
            team_sections.append(element.text.strip())
    
    # Look for sections with team heading
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
    for heading in headings:
        if any(keyword in heading.text.lower() for keyword in team_keywords):
            # Get the next siblings until the next heading
            content = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h1', 'h2', 'h3', 'h4']:
                    break
                if sibling.text.strip():
                    content.append(sibling.text.strip())
            if content:
                team_sections.append(' '.join(content))
    
    # Extract team members specifically
    team_members = []
    
    # Look for common team member structures
    member_elements = soup.find_all(class_=re.compile(r'team-member|member|profile|person', re.I))
    for element in member_elements:
        name = None
        role = None
        
        # Try to find name and role
        name_elem = element.find(['h3', 'h4', 'h5', 'strong', 'b'])
        if name_elem:
            name = name_elem.text.strip()
        
        # Try to find role
        role_elem = element.find(['p', 'span', 'div'], class_=re.compile(r'role|position|title', re.I))
        if role_elem:
            role = role_elem.text.strip()
        elif name and element.find('p'):
            role = element.find('p').text.strip()
        
        if name:
            member_info = name
            if role:
                member_info += f" - {role}"
            team_members.append(member_info)
    
    # Add team members to sections
    if team_members:
        team_sections.append("Team Members: " + ", ".join(team_members))
    
    # Combine and clean
    team_info = ' '.join(team_sections)
    team_info = re.sub(r'\s+', ' ', team_info).strip()
    
    # Truncate if too long
    if len(team_info) > 1000:
        team_info = team_info[:997] + "..."
    
    return team_info if team_info else "No team information found"

def extract_tokenomics(soup):
    """Extract tokenomics information from website"""
    tokenomics_sections = []
    
    # Common tokenomics section identifiers
    tokenomics_keywords = ['tokenomics', 'token', 'distribution', 'allocation', 'supply', 'economics']
    
    # Try to find tokenomics section by ID or class
    for keyword in tokenomics_keywords:
        # Try id
        tokenomics_element = soup.find(id=re.compile(f".*{keyword}.*", re.I))
        if tokenomics_element:
            tokenomics_sections.append(tokenomics_element.text.strip())
            
        # Try class
        tokenomics_elements = soup.find_all(class_=re.compile(f".*{keyword}.*", re.I))
        for element in tokenomics_elements:
            tokenomics_sections.append(element.text.strip())
    
    # Look for sections with tokenomics heading
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
    for heading in headings:
        if any(keyword in heading.text.lower() for keyword in tokenomics_keywords):
            # Get the next siblings until the next heading
            content = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h1', 'h2', 'h3', 'h4']:
                    break
                if sibling.text.strip():
                    content.append(sibling.text.strip())
            if content:
                tokenomics_sections.append(' '.join(content))
    
    # Look for specific tokenomics patterns
    supply_pattern = re.compile(r'(total|max|circulating)?\s*supply\s*:?\s*[\d,]+', re.I)
    supply_matches = []
    for tag in soup.find_all(['p', 'div', 'span', 'li']):
        if supply_pattern.search(tag.text):
            supply_matches.append(tag.text.strip())
    
    if supply_matches:
        tokenomics_sections.append("Supply information: " + " | ".join(supply_matches))
    
    # Combine and clean
    tokenomics_info = ' '.join(tokenomics_sections)
    tokenomics_info = re.sub(r'\s+', ' ', tokenomics_info).strip()
    
    # Truncate if too long
    if len(tokenomics_info) > 1000:
        tokenomics_info = tokenomics_info[:997] + "..."
    
    return tokenomics_info if tokenomics_info else "No tokenomics information found"

def scrape_website(url):
    """Scrape website for project information"""
    if not url:
        return None
    
    domain = urlparse(url).netloc
    
    # Get domain age
    domain_age = get_domain_age(domain)
    
    try:
        # First try with requests (faster)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            about_text = extract_about_section(soup, url)
            team_info = extract_team_info(soup)
            tokenomics = extract_tokenomics(soup)
            
            return {
                'about_text': about_text,
                'team_info': team_info,
                'tokenomics': tokenomics,
                'domain_age': domain_age
            }
        
        # If requests fails, try with Selenium
        print(f"Requests failed with status {response.status_code}, trying Selenium")
        driver = setup_driver(headless=True)
        
        try:
            driver.get(url)
            time.sleep(5)  # Wait for JavaScript to load
            
            # Scroll down to load lazy content
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            about_text = extract_about_section(soup, url)
            team_info = extract_team_info(soup)
            tokenomics = extract_tokenomics(soup)
            
            return {
                'about_text': about_text,
                'team_info': team_info,
                'tokenomics': tokenomics,
                'domain_age': domain_age
            }
            
        except Exception as e:
            print(f"Selenium scraping error: {e}")
            return {
                'about_text': f"Failed to load content: {str(e)}",
                'team_info': "Not available",
                'tokenomics': "Not available",
                'domain_age': domain_age
            }
        finally:
            driver.quit()
            
    except Exception as e:
        print(f"Website scraping error: {e}")
        return {
            'about_text': f"Failed to access website: {str(e)}",
            'team_info': "Not available",
            'tokenomics': "Not available",
            'domain_age': domain_age
        }

if __name__ == "__main__":
    # Test the scraper with a sample URL
    test_url = "https://example.com"
    print(scrape_website(test_url)) 
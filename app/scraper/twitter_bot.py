"""
Twitter scraper module for AirdropAgent
"""
import sys
import os
import time
import datetime
import re
from urllib.parse import urlparse
import random

# Add root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import TWITTER_USERNAME, TWITTER_PASSWORD, SEARCH_INTERVAL_MINUTES, TWEETS_PER_SEARCH
from app.models.ai_analyzer import analyze_airdrop, extract_website_from_tweet
from app.scraper.website_scraper import scrape_website
import database

class TwitterBot:
    def __init__(self, headless=False):
        """Initialize the Twitter scraper bot"""
        self.headless = headless
        self.driver = None
        self.is_logged_in = False
        
        # Login attempts counter
        self.login_attempts = 0
        self.max_login_attempts = 3
        
        # Initialize the browser
        self.setup_driver()
    
    def setup_driver(self):
        """Set up Chrome WebDriver"""
        options = Options()
        
        if self.headless:
            options.add_argument("--headless")
        
        # Common options to make Selenium more stable
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Optional: disable images for faster loading
        # options.add_argument("--blink-settings=imagesEnabled=false")
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)
    
    def login(self):
        """Login to Twitter with credentials"""
        if self.is_logged_in:
            return True
            
        if self.login_attempts >= self.max_login_attempts:
            print("Maximum login attempts reached. Please check credentials.")
            return False
            
        self.login_attempts += 1
            
        try:
            self.driver.get("https://twitter.com/i/flow/login")
            time.sleep(3)  # Wait for page to load
            
            # Enter username
            username_field = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[autocomplete='username']"))
            )
            username_field.send_keys(TWITTER_USERNAME)
            
            # Click Next
            next_button = self.driver.find_element(By.XPATH, "//div[@role='button'][.//span[text()='Next']]")
            next_button.click()
            
            # Enter password
            password_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
            )
            password_field.send_keys(TWITTER_PASSWORD)
            
            # Click Login
            login_button = self.driver.find_element(By.XPATH, "//div[@role='button'][.//span[text()='Log in']]")
            login_button.click()
            
            # Wait for successful login
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//a[@aria-label='Home' or @aria-label='Home timeline']"))
            )
            
            print("Successfully logged in to Twitter")
            self.is_logged_in = True
            return True
            
        except Exception as e:
            print(f"Failed to login: {e}")
            self.is_logged_in = False
            return False
    
    def search_airdrops(self):
        """Search for airdrop tweets"""
        if not self.is_logged_in and not self.login():
            print("Not logged in. Cannot search.")
            return []
            
        try:
            # Search for #airdrop tweets
            self.driver.get("https://twitter.com/search?q=%23airdrop&src=typed_query&f=live")
            time.sleep(5)  # Wait for results to load
            
            # Scroll to load more tweets
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            
            # Collect tweets
            tweets = self.driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
            print(f"Found {len(tweets)} tweets")
            
            return tweets[:TWEETS_PER_SEARCH]  # Limit to configured number
            
        except Exception as e:
            print(f"Error searching for tweets: {e}")
            self.is_logged_in = False  # Force re-login on next attempt
            return []
    
    def extract_tweet_data(self, tweet_element):
        """Extract data from a tweet element"""
        try:
            # Extract username
            username = tweet_element.find_element(By.XPATH, ".//div[@data-testid='User-Name']").text.split('\n')[0]
            
            # Extract tweet text
            try:
                text_element = tweet_element.find_element(By.XPATH, ".//div[@data-testid='tweetText']")
                tweet_text = text_element.text
            except NoSuchElementException:
                tweet_text = "No text found"
            
            # Extract tweet URL
            try:
                time_element = tweet_element.find_element(By.XPATH, ".//time")
                tweet_url = time_element.find_element(By.XPATH, "./..").get_attribute("href")
            except NoSuchElementException:
                tweet_url = None
            
            # Extract project name from tweet text (basic approach)
            project_name = self.extract_project_name(tweet_text, username)
            
            # Extract website URL from tweet
            website_url = extract_website_from_tweet(tweet_text)
            
            return {
                "username": username,
                "tweet_text": tweet_text,
                "tweet_url": tweet_url,
                "project_name": project_name,
                "website_url": website_url
            }
            
        except Exception as e:
            print(f"Error extracting tweet data: {e}")
            return None
    
    def extract_project_name(self, tweet_text, username):
        """Extract project name from tweet text"""
        # First check for specific formats like "Project: NAME" or "Token: NAME"
        project_match = re.search(r'(?:project|token|airdrop)[:\s]+([A-Za-z0-9]+)', tweet_text, re.IGNORECASE)
        if project_match:
            return project_match.group(1)
            
        # Try extracting from cashtags
        cashtags = re.findall(r'\$([A-Za-z0-9]+)', tweet_text)
        if cashtags:
            return cashtags[0]
            
        # Try extracting from website domain
        website_url = extract_website_from_tweet(tweet_text)
        if website_url:
            domain = urlparse(website_url).netloc
            parts = domain.split('.')
            if len(parts) > 1:
                return parts[-2].capitalize()  # Return domain name without TLD
        
        # Fallback to first part of username
        return username.split('@')[0] if '@' in username else username
    
    def process_airdrop_tweets(self):
        """
        Process airdrop tweets: search, extract data, analyze with AI, and save to database
        Returns the number of processed tweets
        """
        tweets = self.search_airdrops()
        processed_count = 0
        
        for tweet in tweets:
            try:
                tweet_data = self.extract_tweet_data(tweet)
                
                if not tweet_data or len(tweet_data["tweet_text"]) < 30:
                    continue
                    
                # Skip if not relevant to airdrops
                if not any(keyword in tweet_data["tweet_text"].lower() for keyword in 
                           ['airdrop', 'token', 'claim', 'free', 'reward', 'crypto']):
                    continue
                
                print(f"Processing tweet from {tweet_data['username']} about {tweet_data['project_name']}")
                
                # Scrape project website if available
                website_data = None
                if tweet_data["website_url"]:
                    website_data = scrape_website(tweet_data["website_url"])
                
                # Get AI analysis
                analysis = analyze_airdrop(
                    tweet_data["tweet_text"], 
                    tweet_data["project_name"],
                    website_data
                )
                
                # Save to database
                airdrop_id = database.save_airdrop_analysis(
                    project_name=tweet_data["project_name"],
                    username=tweet_data["username"],
                    tweet_text=tweet_data["tweet_text"],
                    tweet_url=tweet_data["tweet_url"],
                    website_url=tweet_data["website_url"],
                    rating=analysis['rating'],
                    analysis=analysis['analysis'],
                    is_scam=analysis['is_scam']
                )
                
                # If we have website data, save it too
                if website_data and airdrop_id:
                    database.save_website_data(
                        project_id=airdrop_id,
                        about_text=website_data.get('about_text', ''),
                        team_info=website_data.get('team_info', ''),
                        tokenomics=website_data.get('tokenomics', ''),
                        domain_age=website_data.get('domain_age', '')
                    )
                
                processed_count += 1
                
                # Add some random delay to avoid rate limiting
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"Error processing tweet: {e}")
                continue
        
        return processed_count
    
    def run_monitoring_loop(self):
        """Run the monitoring loop"""
        while True:
            try:
                print(f"Starting airdrop search at {datetime.datetime.now()}")
                
                if not self.is_logged_in:
                    if not self.login():
                        # If login fails, wait and try again
                        print("Login failed. Waiting before retry...")
                        time.sleep(60)
                        continue
                
                processed_count = self.process_airdrop_tweets()
                print(f"Processed {processed_count} airdrop tweets")
                
                # Wait for the configured interval
                print(f"Waiting {SEARCH_INTERVAL_MINUTES} minutes before next search")
                time.sleep(SEARCH_INTERVAL_MINUTES * 60)
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                self.is_logged_in = False  # Force re-login
                time.sleep(60)  # Wait a minute before retrying
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()


def start_twitter_monitoring(headless=True):
    """Start the Twitter monitoring process"""
    bot = TwitterBot(headless=headless)
    try:
        bot.run_monitoring_loop()
    except KeyboardInterrupt:
        print("Monitoring stopped by user")
    finally:
        bot.close()

if __name__ == "__main__":
    start_twitter_monitoring() 
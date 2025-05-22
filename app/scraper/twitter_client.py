"""
Twitter client module for AirdropAgent using Twikit
"""
import sys
import os
import asyncio
import datetime
import re
from urllib.parse import urlparse
import json

# Add root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from twikit import Client
from config import TWITTER_USERNAME, TWITTER_PASSWORD, TWITTER_EMAIL, SEARCH_INTERVAL_MINUTES, TWEETS_PER_SEARCH
from app.models.ai_analyzer import analyze_airdrop, extract_website_from_tweet
from app.scraper.website_scraper import scrape_website
import database

class TwitterClient:
    def __init__(self, language="en-US"):
        """Initialize the Twitter client"""
        self.client = Client(language)
        self.is_logged_in = False
        self.login_attempts = 0
        self.max_login_attempts = 3
        self.cookies_file = 'twitter_cookies.json'
    
    async def login(self):
        """Login to Twitter with credentials"""
        if self.is_logged_in:
            return True
            
        if self.login_attempts >= self.max_login_attempts:
            print("Maximum login attempts reached. Please check credentials.")
            return False
            
        self.login_attempts += 1
            
        try:
            await self.client.login(
                auth_info_1=TWITTER_USERNAME,
                auth_info_2=TWITTER_EMAIL,
                password=TWITTER_PASSWORD,
                cookies_file=self.cookies_file
            )
            
            print("Successfully logged in to Twitter")
            self.is_logged_in = True
            return True
            
        except Exception as e:
            print(f"Failed to login: {e}")
            self.is_logged_in = False
            return False
    
    async def search_airdrops(self):
        """Search for airdrop tweets"""
        if not self.is_logged_in and not await self.login():
            print("Not logged in. Cannot search.")
            return []
            
        try:
            # Search for #airdrop tweets
            tweets = await self.client.search_tweet('#airdrop', 'Latest')
            print(f"Found {len(tweets)} tweets")
            
            return tweets[:TWEETS_PER_SEARCH]  # Limit to configured number
            
        except Exception as e:
            print(f"Error searching for tweets: {e}")
            self.is_logged_in = False  # Force re-login on next attempt
            return []
    
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
    
    async def process_airdrop_tweets(self):
        """
        Process airdrop tweets: search, extract data, analyze with AI, and save to database
        Returns the number of processed tweets
        """
        tweets = await self.search_airdrops()
        processed_count = 0
        
        for tweet in tweets:
            try:
                # Extract basic tweet information
                username = tweet.user.name
                tweet_text = tweet.text
                tweet_id = tweet.id
                tweet_url = f"https://twitter.com/{tweet.user.screen_name}/status/{tweet_id}"
                
                # Skip if tweet text is too short
                if len(tweet_text) < 30:
                    continue
                    
                # Skip if not relevant to airdrops
                if not any(keyword in tweet_text.lower() for keyword in 
                           ['airdrop', 'token', 'claim', 'free', 'reward', 'crypto']):
                    continue
                
                # Extract project name from tweet text
                project_name = self.extract_project_name(tweet_text, username)
                
                print(f"Processing tweet from {username} about {project_name}")
                
                # Extract website URL from tweet
                website_url = extract_website_from_tweet(tweet_text)
                
                # Scrape project website if available
                website_data = None
                if website_url:
                    website_data = scrape_website(website_url)
                
                # Get AI analysis
                analysis = analyze_airdrop(
                    tweet_text, 
                    project_name,
                    website_data
                )
                
                # Save to database
                airdrop_id = database.save_airdrop_analysis(
                    project_name=project_name,
                    username=username,
                    tweet_text=tweet_text,
                    tweet_url=tweet_url,
                    website_url=website_url,
                    rating=analysis['rating'],
                    analysis=analysis['analysis'],
                    is_scam=analysis['is_scam'],
                    timestamp=datetime.datetime.now()
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
                
                # Add some delay to avoid rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Error processing tweet: {e}")
                continue
        
        return processed_count
    
    async def run_monitoring_loop(self):
        """Run the monitoring loop"""
        while True:
            try:
                print(f"Starting airdrop search at {datetime.datetime.now()}")
                
                if not self.is_logged_in:
                    if not await self.login():
                        # If login fails, wait and try again
                        print("Login failed. Waiting before retry...")
                        await asyncio.sleep(60)
                        continue
                
                processed_count = await self.process_airdrop_tweets()
                print(f"Processed {processed_count} airdrop tweets")
                
                # Wait for the configured interval
                print(f"Waiting {SEARCH_INTERVAL_MINUTES} minutes before next search")
                await asyncio.sleep(SEARCH_INTERVAL_MINUTES * 60)
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                self.is_logged_in = False  # Force re-login
                await asyncio.sleep(60)  # Wait a minute before retrying


async def start_twitter_monitoring():
    """Start the Twitter monitoring process"""
    client = TwitterClient()
    try:
        await client.run_monitoring_loop()
    except KeyboardInterrupt:
        print("Twitter monitoring stopped by user")
    except Exception as e:
        print(f"Error in Twitter monitoring: {e}")


if __name__ == "__main__":
    # Run the Twitter monitoring independently
    asyncio.run(start_twitter_monitoring()) 
"""
Configuration file for AirdropAgent
"""

# Twitter credentials
TWITTER_USERNAME = "svkull13"
TWITTER_PASSWORD = "bhayangkara1"
TWITTER_EMAIL = "svkull13@example.com"  # Email for Twitter account (update with real email)

# OpenRouter API
OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Web server settings
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000

# Database settings
DATABASE_PATH = "data/airdrops.db"

# Scraping settings
SEARCH_INTERVAL_MINUTES = 30
TWEETS_PER_SEARCH = 15

# Admin credentials for web interface
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"  # Change this in production 
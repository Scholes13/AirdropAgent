"""
AI Analyzer module for AirdropAgent
Uses OpenRouter API to access AI models with fallback to heuristic analysis
"""
import requests
import json
import re
import time
import sys
import os
import random

# Add root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import OPENROUTER_API_KEY, OPENROUTER_URL

# Global tracking of successful model - persist across function calls
LAST_SUCCESSFUL_MODEL = None
# Global set of rate-limited models - persist across function calls
RATE_LIMITED_MODELS = set()

def analyze_airdrop(tweet_text, project_name, website_data=None):
    """
    Analyze an airdrop tweet using AI via OpenRouter with fallback to heuristics
    
    Args:
        tweet_text (str): The text of the tweet
        project_name (str): The name of the project
        website_data (dict, optional): Additional data from website scraping
        
    Returns:
        dict: Analysis results including rating, explanation, and scam flag
    """
    # Try to use OpenRouter API first
    try:
        ai_result = analyze_with_openrouter(tweet_text, project_name, website_data)
        if ai_result and ai_result.get('rating') > 0:
            return ai_result
    except Exception as e:
        print(f"OpenRouter API error: {e}. Falling back to heuristic analysis.")
    
    # Fallback to heuristic analysis
    print("Using heuristic analysis as fallback")
    return analyze_with_heuristics(tweet_text, project_name, website_data)

def analyze_with_openrouter(tweet_text, project_name, website_data=None):
    """
    Analyze using OpenRouter API with multiple free model fallbacks
    
    Args:
        tweet_text (str): The text of the tweet
        project_name (str): The name of the project
        website_data (dict, optional): Additional data from website scraping
        
    Returns:
        dict or None: Analysis results or None if all models fail
    """
    global LAST_SUCCESSFUL_MODEL, RATE_LIMITED_MODELS
    
    # Proper headers according to OpenRouter docs
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://generalism.id",  # Your domain for rankings
        "X-Title": "AirdropAgent"                # Your app name for rankings
    }
    
    # Check for Telegram links in the tweet or website
    has_telegram_link = any(x in tweet_text.lower() for x in ['t.me/', 'telegram.me/', 'telegram.org/'])
    website_has_telegram = False
    telegram_only = False
    
    if website_data:
        website_text = website_data.get('about_text', '') + website_data.get('team_info', '') + website_data.get('tokenomics', '')
        website_has_telegram = any(x in website_text.lower() for x in ['t.me/', 'telegram.me/', 'telegram.org/'])
        
        # Check if website points primarily to Telegram instead of having real content
        website_content_size = len(website_text.strip())
        if website_content_size < 500 and website_has_telegram:
            telegram_only = True
    
    # Build prompt based on available data
    if website_data:
        prompt = f"""
        Analyze this cryptocurrency airdrop and determine if it seems legitimate or potentially a scam.
        
        TWEET INFORMATION:
        Tweet: {tweet_text}
        Project: {project_name}
        
        WEBSITE INFORMATION:
        About: {website_data.get('about_text', 'Not available')}
        Team: {website_data.get('team_info', 'Not available')}
        Tokenomics: {website_data.get('tokenomics', 'Not available')}
        Domain Age: {website_data.get('domain_age', 'Not available')}
        
        MAJOR RED FLAGS TO CHECK:
        * Telegram Presence: {"Detected Telegram links in tweet or website - CRITICAL RED FLAG" if has_telegram_link or website_has_telegram else "No Telegram links detected"}
        * Telegram-only Project: {"Project appears to direct users primarily to Telegram instead of having substantial website content - VERY HIGH RISK INDICATOR" if telegram_only else "Project has proper website content"}
        
        IMPORTANT ANALYSIS GUIDANCE:
        1. Projects that primarily direct users to Telegram are approximately 70% likely to be scams
        2. Legitimate projects typically have substantial website content, roadmap, whitepaper, and identifiable team
        3. Be extremely skeptical of projects that have minimal website information but prominently feature Telegram links
        4. Check for signs of urgency, limited spots, or requirements to join Telegram for "free tokens"
        
        Provide a rating from 1-10 (1 being likely scam, 10 being very legitimate).
        Give specific reasons for your rating based on both the tweet and website information.
        Identify any red flags or positive signals.
        Format your response with:
        
        Rating: [number]
        Analysis: [detailed analysis]
        """
    else:
        prompt = f"""
        Analyze this cryptocurrency airdrop tweet and determine if it seems legitimate or potentially a scam:
        
        Tweet: {tweet_text}
        Project: {project_name}
        
        MAJOR RED FLAGS TO CHECK:
        * Telegram Links: {"Detected Telegram links in tweet - CRITICAL RED FLAG" if has_telegram_link else "No Telegram links detected"}
        
        IMPORTANT ANALYSIS GUIDANCE:
        1. Projects that primarily direct users to Telegram are approximately 70% likely to be scams
        2. Be extremely skeptical of tweets that directly link to Telegram groups/channels
        3. Legitimate projects typically have official websites, not just Telegram groups
        4. Check for signs of urgency, limited spots, or requirements to join Telegram for "free tokens"
        5. Consider if the tweet contains sufficient specific information about the project
        
        Provide a rating from 1-10 (1 being likely scam, 10 being very legitimate).
        If the project directs users to Telegram as the primary destination, this should significantly reduce the rating.
        Give specific reasons for your rating.
        Identify any red flags such as urgency, unrealistic promises, suspicious links, etc.
        Format your response with:
        
        Rating: [number]
        Analysis: [detailed analysis]
        """
    
    # List of free models to try (in order of preference)
    free_models = [
        "google/gemini-2.0-flash-exp:free",    # Faster Gemini 2.0 Flash (free experimental version)
        "deepseek/deepseek-r1:free",           # Powerful 671B parameter model (37B active)
        "deepseek/deepseek-chat-v3-0324:free", # 685B parameter DeepSeek V3 model
        "google/gemini-pro",                   # Original Gemini Pro as fallback
        "deepseek-ai/deepseek-chat",           # DeepSeek Chat as alternative
        "mistralai/mistral-7b-instruct",       # Mistral as another fallback
        "openchat/openchat-7b"                 # OpenChat as last resort
    ]
    
    # If we have a successful model from previous calls, try it first
    if LAST_SUCCESSFUL_MODEL and LAST_SUCCESSFUL_MODEL not in RATE_LIMITED_MODELS:
        # Move the successful model to the front of the list
        if LAST_SUCCESSFUL_MODEL in free_models:
            free_models.remove(LAST_SUCCESSFUL_MODEL)
            free_models.insert(0, LAST_SUCCESSFUL_MODEL)
            print(f"Prioritizing previously successful model: {LAST_SUCCESSFUL_MODEL}")
    
    # Try each model until one succeeds
    for model in free_models:
        # Skip models that are known to be rate limited
        if model in RATE_LIMITED_MODELS:
            print(f"Skipping rate-limited model: {model}")
            continue
            
        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 2  # seconds
        
        for retry in range(max_retries):
            try:
                current_delay = base_delay * (2 ** retry)
                
                if retry > 0:
                    print(f"Retry {retry}/{max_retries} for model {model} after {current_delay}s delay")
                else:
                    print(f"Trying model: {model}")
                
                # Proper JSON structure as per OpenRouter docs
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,  # Add some variability but not too much
                    "max_tokens": 1024   # Reasonable limit for response
                }
                
                # Using json parameter instead of data with json.dumps()
                response = requests.post(
                    OPENROUTER_URL, 
                    headers=headers, 
                    json=payload, 
                    timeout=30  # Extended timeout for larger models
                )
                
                # Handle rate limiting specifically
                if response.status_code == 429:
                    error_data = response.json() if response.text else {"error": {"message": "Rate limited"}}
                    print(f"Rate limit hit for model {model}: {error_data}")
                    
                    # Add to rate limited models to skip for this session
                    RATE_LIMITED_MODELS.add(model)
                    
                    # No need to retry this model - move to next
                    break
                
                # Check for successful response
                if response.status_code == 200:
                    result = response.json()
                    
                    if 'choices' in result and len(result['choices']) > 0:
                        analysis = result['choices'][0]['message']['content']
                        
                        # Extract rating using multiple regex patterns to handle different AI output formats
                        # First, try to find a rating with "Rating:" format
                        rating_match = re.search(r'Rating:\s*(\d+(?:\.\d+)?)', analysis, re.IGNORECASE)
                        
                        # If not found, look for patterns like "**Rating:** 2/10"
                        if not rating_match:
                            rating_match = re.search(r'\*\*Rating:\*\*\s*(\d+(?:\.\d+)?)(?:/10)?', analysis, re.IGNORECASE)
                        
                        # If not found, look for any number followed by /10
                        if not rating_match:
                            rating_match = re.search(r'(\d+(?:\.\d+)?)\/10', analysis, re.IGNORECASE)
                        
                        # Extract the rating if found
                        if rating_match:
                            rating = float(rating_match.group(1))
                        else:
                            # Default to 5.0 if no rating can be found
                            print(f"No rating found in output, defaulting to 5.0")
                            rating = 5.0
                        
                        # Ensure rating is within bounds
                        rating = max(1.0, min(10.0, rating))
                        
                        # Determine if the airdrop is a scam based on content analysis, not just the rating
                        # Check for strong indicators in the analysis content
                        is_scam = False
                        
                        # Look for scam-related terms in the conclusion
                        if 'scam' in analysis.lower() or 'suspicious' in analysis.lower():
                            # Count how many times scam-related words appear
                            scam_indicators = ['scam', 'suspicious', 'fraud', 'fake', 'red flag', 'misleading', 
                                              'avoid', 'caution', 'warning']
                            scam_count = sum(analysis.lower().count(indicator) for indicator in scam_indicators)
                            
                            # If there are multiple scam indicators or the rating is low, mark as scam
                            if scam_count > 1 or rating < 4.0:
                                is_scam = True
                        else:
                            # If no explicit scam indicators but rating is very low, still mark as scam
                            is_scam = rating < 4.0
                        
                        # Determine legitimacy based on rating (>7.5 is legitimate)
                        is_legitimate = rating > 7.5
                        
                        print(f"Successfully used model: {model}")
                        print(f"Rating: {rating}, Is Scam: {is_scam}, Is Legitimate: {is_legitimate}")
                        
                        # Update our successful model for future calls
                        LAST_SUCCESSFUL_MODEL = model
                        
                        return {
                            'rating': rating,
                            'analysis': analysis,
                            'is_scam': is_scam,
                            'is_legitimate': is_legitimate
                        }
                    else:
                        print(f"Model {model} returned malformed response: {result}")
                else:
                    print(f"Model {model} returned error status: {response.status_code}")
                    print(f"Error details: {response.text}")
                    
                    # For server errors (5xx), retry with backoff
                    if 500 <= response.status_code < 600:
                        time.sleep(current_delay)
                        continue
                    else:
                        # For other errors, just try the next model
                        break
            
            except requests.exceptions.Timeout:
                print(f"Timeout with model {model} on attempt {retry+1}/{max_retries}")
                time.sleep(current_delay)
                continue
                
            except Exception as e:
                print(f"Error with model {model}: {str(e)}")
                break
            
        # Short delay before trying next model
        time.sleep(1)
    
    # If all models fail, return None to trigger fallback
    print("All models failed or were rate-limited. Using heuristic fallback.")
    return None

def analyze_with_heuristics(tweet_text, project_name, website_data=None):
    """
    Analyze airdrop using rule-based heuristics when AI is unavailable
    
    Args:
        tweet_text (str): The text of the tweet
        project_name (str): The name of the project
        website_data (dict, optional): Additional data from website scraping
        
    Returns:
        dict: Analysis results including rating, explanation, and scam flag
    """
    score = 5.0  # Neutral starting point
    red_flags = []
    positive_signals = []
    
    # Convert text to lowercase for case-insensitive matching
    tweet_lower = tweet_text.lower()
    
    # Check for Telegram links - MAJOR RED FLAG
    if any(x in tweet_lower for x in ['t.me/', 'telegram.me/', 'telegram.org/']):
        score -= 3.0  # Heavy penalty for Telegram links
        red_flags.append("Links directly to Telegram - major red flag (70% of Telegram-focused airdrops are scams)")
    
    # Website checks for Telegram focus
    if website_data:
        website_text = website_data.get('about_text', '') + website_data.get('team_info', '') + website_data.get('tokenomics', '')
        website_text_lower = website_text.lower()
        
        if any(x in website_text_lower for x in ['t.me/', 'telegram.me/', 'telegram.org/']):
            # Check if website's main content is minimal but has Telegram links
            if len(website_text.strip()) < 500:
                score -= 2.5
                red_flags.append("Website has minimal content but prominently features Telegram links")
            else:
                score -= 1.0
                red_flags.append("Website includes Telegram links")
    
    # Check tweet text for scam indicators
    if re.search(r'urgently?|hurry|limited time|ending soon|last chance', tweet_lower):
        score -= 1.0
        red_flags.append("Uses urgency tactics")
    
    if re.search(r'guaranteed|100%|certain|definitely', tweet_lower):
        score -= 1.0
        red_flags.append("Makes unrealistic guarantees")
    
    if re.search(r'\$\d+[km]|\d+[km] usd|\d+[km] dollars', tweet_lower):
        score -= 0.5
        red_flags.append("Mentions specific large amounts of money")
    
    if "just send" in tweet_lower or "send your" in tweet_lower:
        score -= 2.0
        red_flags.append("Asks to send crypto/tokens")
    
    if "password" in tweet_lower or "seed phrase" in tweet_lower or "private key" in tweet_lower:
        score -= 3.0
        red_flags.append("Requests sensitive wallet information")
    
    # Positive signals in tweet
    if re.search(r'proof of|kyc|audit|verified', tweet_lower):
        score += 0.5
        positive_signals.append("Mentions verification or audit")
    
    if re.search(r'github|whitepaper|docs|documentation', tweet_lower):
        score += 1.0
        positive_signals.append("References technical documentation")
    
    if re.search(r'community|discord|roadmap', tweet_lower):
        score += 0.5
        positive_signals.append("Has active community channels")
        
    # Check for official website versus only social media
    website_url = extract_website_from_tweet(tweet_text)
    if not website_url:
        score -= 1.0
        red_flags.append("No official website mentioned in tweet")
        
    # Check for mentions of specific blockchain technology
    if "solana" in tweet_lower or "$sol" in tweet_lower or "#sol" in tweet_lower:
        # Currently, legitimate airdrops tend to be on Solana
        score += 0.2
        positive_signals.append("Project built on Solana blockchain")
    
    # Check website data if available
    if website_data:
        domain_age = website_data.get('domain_age', '')
        
        # Try to extract days from domain age
        days_match = re.search(r'(\d+) days', domain_age)
        if days_match:
            days = int(days_match.group(1))
            if days < 30:
                score -= 1.5
                red_flags.append(f"Domain is very new ({days} days old)")
            elif days < 90:
                score -= 0.5
                red_flags.append(f"Domain is relatively new ({days} days old)")
            elif days > 365:
                score += 1.0
                positive_signals.append(f"Domain is well-established ({days} days old)")
        
        # Check for team information
        team_info = website_data.get('team_info', '')
        if team_info and team_info != "No team information found":
            if len(team_info) > 100:  # Substantive team info
                score += 1.0
                positive_signals.append("Has detailed team information")
        else:
            score -= 1.0
            red_flags.append("Missing team information")
        
        # Check tokenomics
        tokenomics = website_data.get('tokenomics', '')
        if tokenomics and tokenomics != "No tokenomics information found":
            if len(tokenomics) > 100:  # Substantive tokenomics
                score += 1.0
                positive_signals.append("Has detailed tokenomics information")
        else:
            score -= 0.5
            red_flags.append("Missing tokenomics information")
    
    # Add a small random factor to avoid all projects having the exact same score
    score += random.uniform(-0.5, 0.5)
    
    # Ensure score is within bounds
    score = max(1.0, min(10.0, score))
    
    # Build analysis text
    analysis = f"Rating: {score:.1f}\n\nAnalysis:\n"
    
    if red_flags:
        analysis += "\nRed Flags:\n" + "\n".join(f"- {flag}" for flag in red_flags)
    
    if positive_signals:
        analysis += "\n\nPositive Signals:\n" + "\n".join(f"- {signal}" for signal in positive_signals)
    
    if not red_flags and not positive_signals:
        analysis += "\nNeutral assessment: Not enough information to determine legitimacy."
    
    if score < 4.0:
        analysis += "\n\nConclusion: This appears to be potentially suspicious or a scam."
    elif score > 7.0:
        analysis += "\n\nConclusion: This appears to be likely legitimate."
    else:
        analysis += "\n\nConclusion: Exercise caution and do further research before participating."
    
    # Determine scam status based on score and analysis content
    is_scam = False
    
    # Use score for baseline classification
    if score < 4.0:
        is_scam = True
    # Count red flags vs positive signals
    elif len(red_flags) > len(positive_signals) + 1:
        is_scam = True
    # Special case for Telegram-focused projects
    elif any(x in tweet_lower for x in ['t.me/', 'telegram.me/', 'telegram.org/']):
        # Higher threshold for Telegram projects - must be very strong otherwise
        if score < 6.0:
            is_scam = True
    
    # Determine if legitimate based on high score (>7.5)
    is_legitimate = score > 7.5
    
    print(f"Heuristic analysis - Rating: {score}, Is Scam: {is_scam}, Is Legitimate: {is_legitimate}")
        
    return {
        'rating': score,
        'analysis': analysis,
        'is_scam': is_scam,
        'is_legitimate': is_legitimate
    }

def extract_website_from_tweet(tweet_text):
    """
    Extract website URL from tweet text
    
    Args:
        tweet_text (str): The text of the tweet
        
    Returns:
        str or None: Extracted website URL or None if not found
    """
    # Common URL patterns
    url_pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)'
    
    urls = re.findall(url_pattern, tweet_text)
    
    # Filter out common non-project URLs
    filtered_urls = [url for url in urls if not any(domain in url.lower() for domain in 
                     ['twitter.com', 't.co', 'bit.ly', 'tinyurl.com'])]
    
    return filtered_urls[0] if filtered_urls else None 
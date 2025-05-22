"""
Main script for AirdropAgent
This script runs both the Twitter monitor and web server
"""
import os
import sys
import time
import threading
import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("airdrop_agent.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("AirdropAgent")

# Import Twitter client
from app.scraper.twitter_client import start_twitter_monitoring
# Import web app
from web.app import app
from config import SERVER_HOST, SERVER_PORT

def start_web_server():
    """Start the web server"""
    logger.info("Starting web server on %s:%s", SERVER_HOST, SERVER_PORT)
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)

async def run_twitter_monitor():
    """Run the Twitter monitor in async mode"""
    logger.info("Starting Twitter monitor")
    try:
        await start_twitter_monitoring()
    except Exception as e:
        logger.error("Twitter monitor error: %s", str(e))

def twitter_monitor_thread():
    """Run Twitter monitor in a separate thread using asyncio"""
    asyncio.run(run_twitter_monitor())

def start_watchdog(threads):
    """
    Watchdog to ensure all threads are running
    If a thread dies, it will be restarted
    """
    logger.info("Starting watchdog")
    
    while True:
        for thread_info in threads:
            name, thread_obj, thread_func = thread_info
            
            if not thread_obj.is_alive():
                logger.warning("Thread %s died, restarting", name)
                new_thread = threading.Thread(target=thread_func, name=name)
                new_thread.daemon = True
                new_thread.start()
                
                # Update thread object in the list
                thread_info[1] = new_thread
        
        # Check every 60 seconds
        time.sleep(60)

def main():
    """Main function to start all components"""
    logger.info("AirdropAgent starting at %s", datetime.now())
    
    # Create threads
    web_thread = threading.Thread(target=start_web_server, name="WebServer")
    twitter_thread = threading.Thread(target=twitter_monitor_thread, name="TwitterMonitor")
    
    # Set as daemon threads so they exit when main thread exits
    web_thread.daemon = True
    twitter_thread.daemon = True
    
    # Start threads
    web_thread.start()
    twitter_thread.start()
    
    # Create list of threads for watchdog
    threads = [
        ["WebServer", web_thread, start_web_server],
        ["TwitterMonitor", twitter_thread, twitter_monitor_thread]
    ]
    
    try:
        # Start watchdog in main thread
        start_watchdog(threads)
    except KeyboardInterrupt:
        logger.info("AirdropAgent stopped by user")
        sys.exit(0)

if __name__ == "__main__":
    main() 
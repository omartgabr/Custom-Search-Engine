import requests
from bs4 import BeautifulSoup
import sqlite3
import aiohttp
import asyncio
import async_timeout
import urllib.parse
import sys
import copy 
from functools import reduce 

# Define search engines and block lists
search_engines = {'Google': 'https://www.google.com/search?q=',
                  'DuckDuckGo': 'https://duckduckgo.com/html/?q=',
                  'Bing': 'https://www.bing.com/search?q=',
                  'Yahoo': 'https://search.yahoo.com/search?p=',
                  'Yandex': 'https://yandex.com/search/?text='}
js_engines = ['DuckDuckGo']  # Engines that require JavaScript rendering
block_list = ['cdn-cgi', '/cdn-cgi/', 'javascript:', '#', '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.svg', '.jpg', '.jpeg', '.png', '.gif']
ad_block_list = ['ad', 'ads', 'banner', 'popup', 'doubleclick']  # Common ad-related terms to block

# Special logic for JavaScript handling in DuckDuckGo
def get_js_soup(url):
    # Import selenium only for search engines that load URLs via JavaScript
    import selenium
    from selenium import webdriver
    try: 
        # Define browser using Safari driver 
        browser = webdriver.Safari()
        # Request URL
        browser.get(url)
        # Get HTML from webpage
        soup = BeautifulSoup(browser.page_source, 'html.parser')
        # Quit browser 
        browser.quit()
        return soup
    except selenium.common.exceptions.WebDriverException:
        print('\nWebdriver Exception. Search engine option compatible with Safari only.\n')
        sys.exit(1) 

# Filter function to clean up URL scrape results 
def filter_function(url, block_list, ad_block_list):
    # Check for "http"
    if 'http' not in url: 
        return False
    # Check if included in block_list and ad_block_list
    elif any(blocked in url for blocked in block_list) or any(blocked in url for blocked in ad_block_list):
        return False
    else:
        return True
    
# Additional data transformations for Google searches 
def google_transformer(url):
    return url.split('&sa=')[0]

# Function for finding URLs resulted from search, with associated HTML clean up and filtering 
# Return list of cleaned up URL 
def urls(soup, engine):
    # Find <a> tags used for links, where tags have href attribute from soup object
    all_href = map(lambda x: x.get('href'), soup.find_all('a', href=True))
    # Filter to URL links 
    url = filter(lambda x: filter_function(x, block_list, ad_block_list), all_href)
    # Additional filter for Google searches
    if engine == 'Google':
        url = map(google_transformer, url)
    # Return cleaned up list of URLs 
    return list(map(str, map(lambda x: x.strip('/url?q='), url)))

# Remove duplicate domains from scraped URLs
def remove_dup(urls):
    # Dictionary to hold domain key and URL value 
    new_urls = {}
    # For each URL, check if domain is in dictionary 
    for url in urls:
        parts = urllib.parse.urlparse(url)
        if parts.netloc not in new_urls:
            # Add domain and URL into dictionary 
            new_urls[parts.netloc] = url
    # Return filtered URLs as a list 
    return list(new_urls.values())

# Get raw text from HTML resulting from engine scrape and get first title object in HTML
def get_raw_text(text):
    soup = BeautifulSoup(text, 'html.parser')
    try: 
        title = soup.title.get_text()
    except AttributeError:
        title = "N/A"
    for script in soup(['script', 'style', 'template', 'TemplateString', 'ProcessingInstruction', 'Declaration', 'Doctype']):
        script.extract()
    text = [item.text.strip().replace(u'\xa0', u' ') for item in soup.find_all('p')]
    return reduce(lambda x, y: x + ' ' + y, text, ''), title 

# Async function to get HTML from URL 
async def get_html(session, url):
    # Get HTML text from session object 
    try:
        async with async_timeout.timeout(10):
            async with session.get(url) as response:
                return await response.text(), url
    # If timeout, return "TimeoutError" and URL as tuple 
    except asyncio.exceptions.TimeoutError:
        return "Error: Timeout", url
    # If invalid URL, return "InvalidURL" and URL as tuple 
    except aiohttp.client_exceptions.InvalidURL:
        return "Error: InvalidURL", url 
    # If server disconnected, return "ServerDisconnected" and URL as tuple
    except aiohttp.client_exceptions.ServerDisconnectedError:
        return 'Error: ServerDisconnected', url 
    except UnicodeDecodeError:
        return 'Error: UnicodeDecodeError', url
    except aiohttp.client_exceptions.ClientConnectorError:
        return 'Error: ClientConnectorError', url
    
# Define tasks for the URLs 
async def get_all(session, urls):
    tasks = []
    # For each URL, create a task to get HTML for the defined session object and URL 
    for url in urls:
        task = asyncio.create_task(get_html(session, url))
        tasks.append(task)
    # Return all the tasks 
    results = await asyncio.gather(*tasks)
    return results 

# Define function to call async functions 
async def async_main(urls):
    # Context manager for aiohttp session object 
    async with aiohttp.ClientSession() as session:
        # Get data obtained from get_all with defined session object and URLs 
        data = await get_all(session, urls)
        # Return list of data, where each element is a tuple containing HTML, URL 
        return data

# Function for executing SQL queries
def sql_execute(cursor, query, input, get_lastrowid=False):
    cursor.execute(query, input)
    if get_lastrowid: 
        return cursor.lastrowid

# Data filter to ensure content going into database is clean 
def data_filter(query, title, text):
    # Lowercase inputs 
    query = query.lower()
    title = title.lower()
    text = text.lower()
    # List for filtering 
    data_filter = ['filter_word1', 'filter_word2']  # Define your filter words here
    # If length of text is less than 50, then will not insert into DB, since it likely is a 404, JavaScript, etc. issue; also filter for words in data_filter
    if len(text) < 50:
        return True
    # Check if any of the filter keywords are in the query. If so, remove those keywords from the filter list 
    if any(term in query for term in data_filter):
        for term in copy.deepcopy(data_filter):
            if term in query:
                data_filter.remove(term)
    # Check if any of the remaining filter keywords are in the title, if so return false. Else return true
    if any(term in title for term in data_filter):
        return True
    else:
        return False 

def populate_database(input_query, engine):
    if engine not in js_engines:
        # Request HTML from web search
        r = requests.get(search_engines[engine] + input_query, headers={'user-agent': 'my-app/0.0.1'})
        # Create BeautifulSoup object 
        soup = BeautifulSoup(r.text, 'html.parser')
    else:
        # Use special handling for JavaScript 
        soup = get_js_soup(search_engines[engine] + input_query)

    # Get scraped URLs, while removing duplicate domains 
    url_list = remove_dup(urls(soup, engine))

    # Asynchronously get HTML text from URLs obtained via search engine scrape
    text_url = asyncio.run(async_main(url_list))

    # Return cleaned up text as a tuple with the URL
    cleaned_text_url = map(lambda x: (get_raw_text(x[0]), x[1]), text_url)

    # Opening connection to SQLite database
    connection = sqlite3.connect('custom_search_engine.db')
    # Creating cursor handler for inserting data 
    cursor = connection.cursor()

    # Query for adding search info
    last_search_id = sql_execute(cursor, 'INSERT INTO searches (search_query, search_engine) VALUES (?, ?)', (input_query, engine), get_lastrowid=True)

    # Inserting URL info
    for text_title, url in cleaned_text_url:
        # Unpack text_title 
        text, title = text_title
        # Additional filtering 
        if data_filter(input_query, title, text):
            continue
        print("\nInserting URL info into 'search_results' table:")
        print("URL:", url)
        print("Last Search ID:", last_search_id)
        print("Title:", title)
        print("Description:", text)
        # Restricting size of text for database constraint
        if len(text) > 60000:
            text = text[:60000]
        # Execute query to add info to search engine tables
        sql_execute(cursor, 'INSERT INTO search_results (url, id, title, description) VALUES (?, ?, ?, ?)', (url, last_search_id, title, text))
            
    # Commit data to database 
    connection.commit()

    # Closing cursor and connection 
    cursor.close()
    connection.close()
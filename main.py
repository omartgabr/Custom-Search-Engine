import os
import sys
import sqlite3
import requests
import urllib.parse
from flask import Flask, request, render_template
from urllib.parse import urlparse
from search_functions import search_engines, filter_and_parse_results

# Define the database file path relative to the current file
db_file = "custom_search_engine.db"

# Initialize set to store domain names
domain_names = set()

# Define the Flask app
app = Flask(__name__,)


# Enable debug mode
app.debug = True

# Define the route for the search page
@app.route('/', methods=['GET', 'POST'])
def index():
    # Get the search query from the form
    if request.method == 'POST':
        search_query = request.form['query']

        # Connect to the SQLite database
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Process each search engine
        for engine, url_format in search_engines.items():
            # Fetch the search engine URL format
            url_format = search_engines.get(engine)
        
            # Construct the search URL and perform the search
            query = {'q': search_query}
            search_url = url_format + urllib.parse.urlencode(query)
            response = requests.get(search_url)
        
            # Parse the HTML response and filter the search results
            results = filter_and_parse_results(response, engine, search_query)
        
            # Process each search result and add it to the database
            for result in results:
                url = result[0]
                title = result[3]
                text_data = result[4]
                search_term_id = None
        
                domain_name = title.split(':')[0]
        
                # Check if the domain name is already in the set
                if domain_name in domain_names:
                    continue  # Skip adding the URL to the database
        
                # Add the domain name to the set
                domain_names.add(domain_name)
        
                # Insert the URL into the database
                add_url = ("INSERT INTO search_term "
                           "(url, search_engine, number_of_search_terms, search) "
                           "VALUES (?, ?, ?, ?)")
                try:
                    cursor.execute(add_url, (url, engine, len(search_query.split()), search_query))
                    conn.commit()
                    search_term_id = cursor.lastrowid
                except sqlite3.Error as err:
                    print("Error:", err)
        
                # Get the info type of the URL content
                info_type = result[5]
        
                # Insert the parsed URL data into the database
                add_parsed_url = ("INSERT INTO parsed_url "
                                  "(Results_ID, title, description, info_type) "
                                  "VALUES (?, ?, SUBSTR(?, 1, 500), ?)")
                cursor.execute(add_parsed_url, (search_term_id, title, text_data, info_type))
                conn.commit()
        
                # Compute the occurrence count of search terms and insert them into the database
                search_terms = search_query.lower().split()
                for term in search_terms:
                    count = 0
                    for result in results:
                        if term in result[3].lower() or term in result[4].lower():
                            count += 1
        
                    # Insert the occurrence count into the database
                    add_url_stats = ("INSERT INTO url_stats "
                                     "(Stats_ID, stats_url, occurrence_count) "
                                     "VALUES (?, ?, ?)")
                    cursor.execute(add_url_stats, (search_term_id, url, count))
                    conn.commit()
        
        # Fetch the search results from the database
        select_urls = ("SELECT DISTINCT search_term.url, parsed_url.title, parsed_url.description, parsed_url.info_type, search_term.search_engine, url_stats.occurrence_count "
                       "FROM search_term "
                       "JOIN parsed_url ON search_term.id = parsed_url.Results_ID "
                       "LEFT JOIN url_stats ON search_term.id = url_stats.Stats_ID AND search_term.url = url_stats.stats_url "
                       "WHERE search_term.search = ? "
                       "ORDER BY url_stats.occurrence_count DESC")
        cursor.execute(select_urls, (search_query,))
        rows = cursor.fetchall()
    
        # Filter the search results to remove URLs with duplicate domain names
        filtered_results = []
        visited_domains = set()
    
        for result in rows:
            url = result[0]
            domain = urlparse(url).netloc
            if domain not in visited_domains:
                filtered_results.append(result)
                visited_domains.add(domain)
    
        # Close the database connection
        cursor.close()
        conn.close()
    

        # Render the search results template with the filtered list of URLs
        return render_template("results.html", query=search_query, rows=filtered_results)

    # If the request method is GET, render the search page
    # Fetch recent search queries
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    fetch_recent_searches = "SELECT search_query FROM recent_searches ORDER BY search_date DESC LIMIT 10"
    cursor.execute(fetch_recent_searches)
    recent_searches = [row[0] for row in cursor.fetchall()]

    # Close the database connection
    cursor.close()
    conn.close()

    # Render the search page template
    return render_template("search.html", recent_searches=recent_searches)

if __name__ == '__main__':
    app.run()

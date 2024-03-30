import os
import sys
import sqlite3
import requests
import urllib.parse
from flask import Flask, request, render_template
from search_functions import get_js_soup, filter_function, google_transformer, remove_dup, get_raw_text, get_all, async_main, sql_execute, data_filter, populate_database
from data_processing import remove_stop_words, keyword_count, dict_to_tuple, search
from configuration import add_search_query, add_search_result, get_info

# Define the search engines and their corresponding URLs
browsers = {'Google': 'https://www.google.com/search?q=',
            'DuckDuckGo': 'https://duckduckgo.com/html/?q=',
            'Bing': 'https://www.bing.com/search?q=',
            'Yahoo': 'https://search.yahoo.com/search?p=',
            'Yandex': 'https://yandex.com/search/?text='}

# Define the database file path relative to the current file
db_file = "custom_search_engine.db"

# Define the Flask app
app = Flask(__name__)

# Enable debug mode
app.debug = True

# Define the route for the search page
@app.route('/', methods=['GET', 'POST'])
def index():
    # Get the search query from the form
    if request.method == 'POST':
        search_query = request.form['query']

        # Loop through each engine and populate the database based on the query and engine
        for engine, url in browsers.items():
            print('Populating database for ' + engine + '...')
            add_search_query(search_query, engine)
            search_results = get_info(search_query, engine)
            for url in search_results:
                add_search_result(url, search_query, '', '')  # Add website title and raw text as needed

        # Render the search results template
        return render_template("results.html", query=search_query, rows=search_results)

    # If the request method is GET, render the search page
    # Render the search page template
    return render_template("search.html", engines=browsers.keys())

if __name__ == '__main__':
    app.run()

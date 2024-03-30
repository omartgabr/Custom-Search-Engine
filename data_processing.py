from collections import Counter
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import sqlite3

# Function for removing stopwords from passed text 
def remove_stop_words(text, stop_words):
    tokens = word_tokenize(text)
    return [w for w in tokens if not w.lower() in stop_words]

# Function to count the occurrences of keywords 
def keyword_count(keywords, text):
    kw_dict = dict()
    c = Counter(s.lower() for s in text.split())
    for term in keywords:
        kw_dict[term] = c[term.lower()]
    return kw_dict

def dict_to_tuple(d):
    keys = list(d.keys())
    values = list(d.values())
    sum_counts = sum(values)
    return sorted(tuple(zip(keys, values)), key=lambda x: -x[1]), sum_counts

# Function for performing search in the SQLite database
def search(query, db_file): 
    # Downloading necessary NLTK data
    nltk.download('stopwords')
    nltk.download('punkt')
    # Get stop_words from NLTK
    stop_words = set(stopwords.words('english'))
    # Get keywords from query 
    query_keywords = remove_stop_words(query, stop_words)

    # Get connection 
    connection = sqlite3.connect(db_file)
    # Get cursor for executing commands with SQL DB 
    cursor = connection.cursor()
    # Query 
    cursor.execute('''SELECT title, description 
                      FROM search_results 
                      WHERE description LIKE ?''', ('%' + query + '%',))
    # Get all results
    results = cursor.fetchall()
    
    # Perform keyword operations and formatting on results 
    formatted_results = []
    for title, description in results:
        # Combine title and description for text processing
        text = title + ' ' + description
        # Calculate keyword count
        keyword_counts = keyword_count(query_keywords, text)
        # Convert keyword count to tuple for sorting
        keyword_counts_tuple, total_count = dict_to_tuple(keyword_counts)
        # Append formatted result to list
        formatted_results.append((title, description, keyword_counts_tuple, total_count))

    # Sort by descending total keyword count
    formatted_results = sorted(formatted_results, key=lambda x: -x[3])

    # Close cursor and connection
    cursor.close()
    connection.close()
    
    # Return results 
    return formatted_results
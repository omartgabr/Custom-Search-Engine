import requests
import re
from bs4 import BeautifulSoup
import mysql.connector
import urllib.parse
from urllib.parse import urlparse
from flask import Flask, request, render_template
import io
from PyPDF2 import PdfReader
import pytesseract

# Define the database connection details
config = {
    'user': 'root',
    'password': '*KitboGa1701*',
    'host': '127.0.0.1',
    'database': 'my_custom_bot'
}


# Define the search engines and their URL format
search_engines = {
    "google": "https://www.google.com/search?q=",
    "bing": "https://www.bing.com/search?q=",
    "yahoo": "https://search.yahoo.com/search?p="
}


def perform_ocr_on_pdf(pdf_data):
    try:
        with io.BytesIO(pdf_data) as pdf_file:
            pdf_reader = PdfReader(pdf_file)
            text = ''
            for page in pdf_reader.pages:
                text += page.extract_text()
            paragraphs = text.split('\n\n')
            return '\n\n'.join(paragraphs[:2]).encode('utf-8')
    except Exception as e:
        print("An error occurred while trying to extract text from the PDF:", e)
        return None

def extract_text_from_image(image_data):
    try:
        # Extract text from image using pytesseract
        text = pytesseract.image_to_string(image_data, lang='eng')
        paragraphs = text.split('\n\n')
        return '\n\n'.join(paragraphs[:2]).encode('utf-8')
    except Exception as e:
        print("An error occurred while trying to extract text from the image:", e)
        return None


def filter_and_parse_results(response, engine, query):
    soup = BeautifulSoup(response.text, 'html.parser')
    results = []
    
    if engine == "google":
        for i in soup.find_all('a', href=True):
            url = i['href']
            # Skip specific websites
            if "accounts.google.com" in url or "support.google.com" in url:
                continue
            if url.startswith('/url?q='):
                # Extract the URL and other relevant information
                link = url.split('/url?q=')[1].split('&sa=U&')[0]
                title_el = i.find('h3') or i.find('h2') or i.find('h1') or i.find('title')
                if title_el:
                    title = title_el.get_text()
                else:
                    domain = urlparse(link).netloc
                    title = domain.split('.')[0].capitalize()
    
                # Perform the Google search
                try:
                    page = requests.get(link)
                    soup = BeautifulSoup(page.content, "html.parser")
    
                    text_elements = soup.find_all("p")
                    text_data = "\n".join([element.text.strip() for element in text_elements])
                except Exception as e:
                    print("An error occurred while processing the URL:", link)
                    print("Error:", e)
                    # Set the text_data to 'No Description' if an error occurs
                    text_data = 'No Description'

                # Check if the URL is a PDF or image
                if link.endswith('.pdf'):
                    info_type = 'PDF'
                    try:
                        # Extract text from PDF using OCR
                        pdf_response = requests.get(link, stream=True)
                        pdf_data = pdf_response.content
                        ocr_response = perform_ocr_on_pdf(pdf_data)
                        text_data = ocr_response.decode('utf-8')
                        info_type = 'OCR_text'
                    except:
                        pass
                elif link.endswith('.png') or link.endswith('.jpg') or link.endswith('.jpeg') or link.endswith('.gif'):
                    info_type = 'Image'
                    try:
                        # Extract text from image using OCR
                        image_response = requests.get(link, stream=True)
                        image_data = image_response.content
                        text_data = extract_text_from_image(image_data)
                        info_type = 'OCR_text'
                    except:
                        pass
                else:
                    info_type = 'Text'

                # Extract the domain name from the URL
                domain_name = urlparse(link).netloc
                domain_name = domain_name.split('www.')[-1].split('.')[0]

                # Format the title
                formatted_title = f"{domain_name}: {title}"

                results.append((link, 'Google', len(query.split()), formatted_title, text_data, info_type))
    
    elif engine == 'bing':
        search_engine_url = search_engines.get(engine)
        headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
        response = requests.get(search_engine_url + urllib.parse.quote(query), headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        for result in soup.find_all('li', {'class': 'b_algo'}):
            url = result.find('a')['href']
            title_el = result.find('a') or result.find('h2') or result.find('h1') or result.find('title')
            if title_el:
                title = title_el.get_text()
            else:
                domain = urlparse(url).netloc
                domain_name = domain.split('www.')[-1].split('.')[0]
                title = f"{domain_name.capitalize()}: {title}"
            text_data_el = result.find('p')
            if text_data_el:
                text_data = text_data_el.get_text()
            else:
                text_data = 'No Description'
            
            # Set the info_type based on the URL type
            if url.endswith('.pdf'):
                info_type = 'PDF'
                try:
                    # Perform OCR on PDF
                    pdf_data = requests.get(url).content
                    ocr_response = perform_ocr_on_pdf(pdf_data)
                    if ocr_response:
                        # If OCR is successful, set info_type to OCR_text
                        info_type = 'OCR_text'
                        # Parse OCR text to store title and description separately
                        decoded_data = ocr_response.decode('utf-8')
                        title = re.findall(r"^(.*)\n", decoded_data)[0]
                        text_data = re.findall(r"\n(.*)", decoded_data)[0]
                except Exception as e:
                    print("An error occurred while trying to extract text from the PDF:", e)
                    # If OCR fails, just store the original text
                    text_data = 'No Description'
            elif url.endswith('.png') or url.endswith('.jpg') or url.endswith('.jpeg') or url.endswith('.gif'):
                info_type = 'Image'
                try:
                    # Extract text from image using OCR
                    img_response = requests.get(url, stream=True)
                    img_data = img_response.content
                    ocr_response = extract_text_from_image(img_data)
                    if ocr_response:
                        # If OCR is successful, set info_type to OCR_text
                        info_type = 'OCR_text'
                        text_data = ocr_response
                except Exception as e:
                    print("An error occurred while trying to extract text from the image:", e)
                    text_data = 'No Description'
            else:
                info_type = 'Text'
            
            results.append((url, 'Bing', len(query.split()), title, text_data, info_type))
    
    elif engine == "yahoo":
        search_engine_url = search_engines.get(engine)
        response = requests.get(search_engine_url + urllib.parse.quote(query))
        soup = BeautifulSoup(response.text, 'html.parser')
        data_block = soup.findAll('div', class_=re.compile("dd algo algo-sr relsrch"))
        for result in data_block:
            title = result.find("h3", {"class": "title"}).text
            link_yahoo = result.find('h3').a['href']
            desc = result.find('div', class_='compText aAbs')
            if desc is None:
                desc = 'No Description'
            else:
                desc = desc.text
    
            # If title is empty, extract the domain name from the URL
            if not title:
                parsed_url = urlparse(link_yahoo)
                title = parsed_url.netloc
    
            # Extract the domain name from the URL
            domain_name = urlparse(link_yahoo).netloc
            domain_name = domain_name.split('www.')[-1].split('.')[0]
    
            # Format the title
            formatted_title = f"{domain_name.capitalize()}: {title}"
    
            # Determine the info type of the URL content
            if link_yahoo.endswith('.pdf'):
                # Download the PDF file
                pdf_response = requests.get(link_yahoo)
                pdf_data = pdf_response.content
                # Perform OCR on the PDF file
                try:
                    ocr_response = perform_ocr_on_pdf(pdf_data)
                    text_data = ocr_response.decode('utf-8') if ocr_response is not None else desc
                    info_type = 'OCR_text'
                except:
                    text_data = desc
                    info_type = 'PDF'
            elif link_yahoo.endswith('.png') or link_yahoo.endswith('.jpg') or link_yahoo.endswith('.jpeg') or link_yahoo.endswith('.gif'):
                info_type = 'Image'
                try:
                    # Extract text from image using OCR
                    image_response = requests.get(link_yahoo, stream=True)
                    image_data = image_response.content
                    ocr_response = extract_text_from_image(image_data)
                    if ocr_response:
                        # If OCR is successful, set info_type to OCR_text
                        info_type = 'OCR_text'
                        text_data = ocr_response
                    else:
                        # If OCR fails, just store the original text
                        text_data = desc
                except Exception as e:
                    print("An error occurred while trying to extract text from the image:", e)
                    text_data = desc
            else:
                info_type = 'Text'
                text_data = desc
    
            results.append((link_yahoo, 'Yahoo', len(query.split()), formatted_title, text_data, info_type))
    
    else:
        raise ValueError("Invalid search engine")
    
    return results



# Initialize set to store domain names
domain_names = set()

# Define the Flask app
app = Flask(__name__)

# Enable debug mode
app.debug = True

# Define the route for the search page
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Get the search query from the form
        search_query = request.form['query']

        # Connect to the database
        cnx = mysql.connector.connect(user=config['user'], password=config['password'], host=config['host'], database=config['database'])
        cursor = cnx.cursor()

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
                           "VALUES (%s, %s, %s, %s)")
                try:
                    cursor.execute(add_url, (url, engine, len(search_query.split()), search_query))
                    cnx.commit()
                    search_term_id = cursor.lastrowid
                except mysql.connector.Error as err:
                    print("Error: {}".format(err))
        
                # Get the info type of the URL content
                info_type = result[5]
        
                # Insert the parsed URL data into the database
                add_parsed_url = ("INSERT INTO parsed_url "
                                  "(Results_ID, title, description, info_type) "
                                  "VALUES (%s, %s, SUBSTRING(%s, 1, 500), %s)")
                cursor.execute(add_parsed_url, (search_term_id, title, text_data, info_type))
                cnx.commit()
        
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
                                     "VALUES (%s, %s, %s)")
                    cursor.execute(add_url_stats, (search_term_id, url, count))
                    cnx.commit()
        
        # Fetch the search results from the database
        select_urls = ("SELECT DISTINCT search_term.url, parsed_url.title, parsed_url.description, parsed_url.info_type, search_term.search_engine, url_stats.occurrence_count "
                       "FROM search_term "
                       "JOIN parsed_url ON search_term.id = parsed_url.Results_ID "
                       "LEFT JOIN url_stats ON search_term.id = url_stats.Stats_ID AND search_term.url = url_stats.stats_url "
                       "WHERE search_term.search = %s "
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
        cnx.close()
    
        # Render the search results template with the filtered list of URLs
        return render_template('results.html', query=search_query, rows=filtered_results)

    # If the request method is GET, render the search page
    # Fetch recent search queries
    cnx = mysql.connector.connect(user=config['user'], password=config['password'], host=config['host'], database=config['database'])
    cursor = cnx.cursor()
    fetch_recent_searches = "SELECT search_query FROM recent_searches ORDER BY search_date DESC LIMIT 10"
    cursor.execute(fetch_recent_searches)
    recent_searches = [row[0] for row in cursor.fetchall()]

    # Close the database connection
    cursor.close()
    cnx.close()

    return render_template('search.html', recent_searches=recent_searches)

                          



if __name__ == '__main__':
    app.run()

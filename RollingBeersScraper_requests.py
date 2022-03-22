#!/usr/bin/python3

# https://elitedatascience.com/python-web-scraping-libraries
from distutils.log import error
from shutil import ExecError
import requests
from bs4 import BeautifulSoup
import re
import json
from json import JSONEncoder
import sys
import threading

from requests.models import Response


class Brand:
    def __init__(self, name, pattern, regex: bool):
        self.name = name
        self.pattern = pattern
        self.regex = regex

    def match(self, brand):
        if self.regex:
            pattern = re.compile(self.pattern)
            match = re.search(pattern, brand)
            if match is not None:
                return True

            # Last chance to get the brand right (sometimes it is not encoded using the brand's regular
            # naming convention, so we have to fallback on this test to get it right !)
            elif brand.upper().find(self.name.upper()) != -1:
                return True
        else:
            if brand.upper().find(self.pattern.upper()) != -1:
                return True
        return False


brands = [
    Brand('Wyeast', 'Wyeast', regex=False),
    Brand('Fermentis', 'SAF', regex=False),
    Brand('White Labs', '.*WL[PN].*', regex=True),
    Brand('Lallemand', 'Lallemand', regex=False),
    Brand('Mangrove Jack\'s', '.*M[0-9]{2}.*', regex=True),
    Brand('Mauribrew', 'Mauribrew', regex=False),
    Brand('Bioferm', 'Bioferm', regex=False),
    Brand('Brewferm', 'Brewferm', regex=False),
]


def remove_latin_escaped(string: str):
    return string.replace(u'\xa0', u' ')


class Yeast:
    def __init__(self):
        self.name = 'Generic yeast'
        self.brand = 'Generic'
        self.link = ''
        self.abv_tol = ''
        self.floculation = '50%'
        self.attenuation_range = ['60%', '70%']
        self.price = '0.00€'
        self.temp_range = ['15°', '18°']
        self.description = ''
        self.patterns = {
            'abv':  re.compile(r"[\D]*([0-9]+%).*"),
            'attenuation':  re.compile(r".*([0-9]{2})-([0-9]{2}).*"),
            'temperature':  re.compile(r".*([0-9]{2})-([0-9]{2}).*"),
            'floculation':  re.compile(r"(.*)")
        }

    def get_dict(self):
        out = self.__dict__.copy()
        out.pop('patterns')
        return out

    def from_json(self, input : dict) :
        self.name = input["name"]
        self.brand = input["brand"]
        self.link = input["link"]
        self.abv_tol = input["abv_tol"]
        self.floculation = input["floculation"]
        self.attenuation_range = input["attenuation_range"]
        self.price = input["price"]
        self.temp_range = input["temp_range"]
        self.description = input["description"]

    def format_data(self):
        # Find Brand from name
        for brand in brands:
            if brand.match(self.name):
                self.brand = brand.name
                break

        # Extract ABV
        self.abv_tol = remove_latin_escaped(self.abv_tol)
        match = re.search(self.patterns['abv'], self.abv_tol)
        if match is not None:
            self.abv_tol = match[1]

        # Extract attenuation
        self.attenuation_range[0] = remove_latin_escaped(
            self.attenuation_range[0])
        match = re.search(
            self.patterns['attenuation'], self.attenuation_range[0])
        if match is not None:
            self.attenuation_range[0] = match[1] + u'%'
            self.attenuation_range[1] = match[2] + u'%'

        # Extract floculation
        self.floculation = remove_latin_escaped(self.floculation)
        match = re.search(self.patterns['floculation'], self.floculation)
        if match is not None:
            self.floculation = match[1]

        # Extract temperature range
        self.temp_range[0] = remove_latin_escaped(self.temp_range[0])
        match = re.search(self.patterns['temperature'], self.temp_range[0])
        if match is not None:
            self.temp_range[0] = match[1] + u'°C'
            self.temp_range[1] = match[2] + u'°C'

        # Format price
        if self.price.find('€') == -1:
            self.price += u'€'

        # https://stackoverflow.com/questions/10993612/how-to-remove-xa0-from-string-in-python
        self.description = self.description.replace(u'\xa0', u' ')
        self.description = self.description.replace('\\', '')

    class YeastEncoder(JSONEncoder):
        def default(self, o):
            outdict = {
                'name': o.name,
                'brand': o.brand,
                'link': o.link,
                'abv': o.abv_tol,
                'floculation': o.floculation,
                'attenuation': [
                    o.attenuation_range[0],
                    o.attenuation_range[1]
                ],
                'price': o.price,
                'temperature': [
                    o.temp_range[0],
                    o.temp_range[1]
                ],
                'description': o.description
            }
            return outdict



class NotAYeastError(Exception):
    def __init__(self, link):
        self.link = link


# Finds all available yeasts with their names and links to their description page
def parse_page(page_link, yeasts : list[Yeast]):

    headersList = {
        "Accept": "*/*",
        "User-Agent": "Thunder Client (https://www.thunderclient.io)"
    }

    response = requests.get(page_link, headers=headersList)
    print("Reading page {}".format(page_link))
    if response.status_code >= 400:
        print("Could not read page, caught error {}".format(response.status_code))
        print("Response error message is {}".format(response.text))
        return ''

    contents = response.content
    soup = BeautifulSoup(contents, 'html.parser')

    for elem in soup.find_all('div', href=False, attrs={'class': 'kl-title-aff'}):
        yeast = Yeast()
        yeast_block = elem.find('a', href=True)
        yeast.name = yeast_block.find(
            'h3', attrs={'itemprop': 'name'}).contents[0]
        yeast.link = yeast_block.attrs['href']
        yeasts.append(yeast)

    next_page = soup.find(
        'a', attrs={'class': 'page-link'}, href=True, string='Suivant')
    if next_page != None:
        return next_page.attrs['href']

    return ''


def parse_yeast(yeast: Yeast):
    headersList = {
        "Accept": "*/*",
        "User-Agent": "Thunder Client (https://www.thunderclient.io)"
    }
    response = requests.get(yeast.link, headers=headersList)
    print("Reading yeast data for {}".format(yeast.name))
    if response.status_code >= 400:
        print("Could not read page, caught error {}".format(response.status_code))
        print("Response error message is {}".format(response.text))
        return yeast

    contents = response.content
    soup = BeautifulSoup(contents, 'html.parser')
    price_div = soup.find('div', attrs={'class': 'current-price'})
    try:
        price_span = price_div.find('span', attrs={'itemprop': 'price'})
        yeast.price = price_span.attrs['content']
    except AttributeError or Exception:
        yeast.price = 'No data'

    name_field = soup.find('h1', attrs={'itemprop': 'name'})
    yeast.name = name_field.next
    description_section = soup.find('section', attrs={'class': 'kl-bg-grey'})
    if description_section is None:
        raise NotAYeastError(yeast.link)

    all_p_blocks = description_section.find_all('p')
    # Shitty code because all yeasts are not all displayed the same way
    try:
        description_block = all_p_blocks[1] if (
            len(all_p_blocks) > 1) else all_p_blocks[0]
        yeast.description = str(
            description_block.next) if description_block.next is not None else ''
    except Exception:
        yeast.description = "Error reading description"

    floculation = description_section.find('strong', string=re.compile("Floculation.*"))
    attenuation = description_section.find('strong', string=re.compile("Atténuation.*"))
    temperature = description_section.find('strong', string=re.compile("Gamme de Température.*"))
    abv = description_section.find('strong', string=re.compile("Tolerance d'alcool.*"))

    try:
        yeast.floculation = floculation.nextSibling
    except (AttributeError):
        yeast.floculation = "NA"
    try:
        yeast.attenuation_range[0] = attenuation.nextSibling
    except (AttributeError):
        yeast.attenuation_range[0] = "NA"
        yeast.attenuation_range[1] = "NA"

    try:
        yeast.temp_range[0] = temperature.nextSibling
    except (AttributeError):
        yeast.temp_range[0] = "NA"
        yeast.temp_range[1] = "NA"

    try:
        yeast.abv_tol = abv.nextSibling
    except (AttributeError):
        yeast.abv_tol = "NA"

    return yeast


def removed_mislabled_yeasts(yeasts_collection : list, mislabled_yeasts : list):
    out_yeasts = []
    for yeast in yeasts_collection:
        mislabled_found = False
        for mislabled in mislabled_yeasts:
            if yeast.name == mislabled.name:
                mislabled_found = True
                break
        if not mislabled_found:
            out_yeasts.append(yeast)
    return out_yeasts

def spread_load_accross_threads(max_threads : int, yeasts : list[Yeast] ) -> list[list[Yeast]] :
    remainder = len(yeasts) % max_threads
    yeasts_per_thread = len(yeasts) // max_threads

    # Collection of yeasts for each thread
    threads_yeast_table : list[list[Yeast]] = []

    current_thread_payload : list[Yeast] = []
    remaining_per_thread = yeasts_per_thread
    i = 0
    while i < len(yeasts) :
        if remaining_per_thread != 0:
            current_thread_payload.append(yeasts[i])
            i += 1
            remaining_per_thread -= 1

            if remaining_per_thread == 0 :
                if remainder > 0:
                    current_thread_payload.append(yeasts[i])
                    i += 1
                    remainder -= 1
                threads_yeast_table.append(current_thread_payload.copy())
                current_thread_payload.clear()
                remaining_per_thread = yeasts_per_thread

    # Append the remaining data, last thread yeast collection
    if len(current_thread_payload) != 0 :
        threads_yeast_table.append(current_thread_payload.copy())

    return threads_yeast_table


def parse_yeasts_threaded(yeasts : list[Yeast], mislabled_yeasts : list[Yeast], error_yeasts : list[Yeast]) :
    mislabled_yeasts = []
    errors_yeasts : list[Yeast] = []
    for yeast in yeasts :
        try:
            yeast = parse_yeast(yeast)
            yeast.format_data()
        except NotAYeastError:
            mislabled_yeasts.append(yeast)
        except Exception :
            errors_yeasts.append(yeast)



def main(args):
    yeasts : list[Yeast] = []
    max_threads = 20

    # Use the pagination item to loop until reaching the end of the catalogue
    # then use each prerecorded link to isolate data from each yeast (abv, floculation, etc...)
    link = "https://www.rolling-beers.fr/fr/55-toutes-les-liquides"
    while link != '':
        link = parse_page(link, yeasts)

    threads_payload_matrix = spread_load_accross_threads(max_threads, yeasts)
    mislabled_yeasts_collection = []
    error_yeasts_collection = []

    # Spread the load on many threads
    threads : list[threading.Thread] = []
    for yeast_payload in threads_payload_matrix :
        mislabled_yeasts : list[Yeast] = []
        error_yeast  : list[Yeast] = []
        mislabled_yeasts_collection.append(mislabled_yeasts)
        error_yeasts_collection.append(error_yeast)
        th = threading.Thread(target=parse_yeasts_threaded, args=(yeast_payload, mislabled_yeasts, error_yeast))
        th.start()
        threads.append(th)

    # Wait for all threads to finish
    joined_thread_count = 0
    joined_threads = []
    while joined_thread_count != len(threads) :
        for thread in threads :
            if not thread.is_alive() and not thread.ident in joined_threads:
                thread.join()
                joined_thread_count += 1
                joined_threads.append(thread.ident)


    # Flattening mislabled yeast collection
    mislabled_yeasts : list[Yeast] = [item for sublist in mislabled_yeasts_collection for item in sublist]
    error_yeasts : list[Yeast] = [item for sublist in error_yeasts_collection for item in sublist]
    yeasts = removed_mislabled_yeasts(yeasts, mislabled_yeasts)
    yeasts = removed_mislabled_yeasts(yeasts, error_yeasts)

    # Dump content to a file
    content = json.dumps([ob.get_dict() for ob in yeasts], indent=4, ensure_ascii=False)
    with open('yeasts.json','w', encoding="utf-8") as file :
        file.writelines(content)

    # Handle errors
    if len(error_yeasts) != 0 :
        print("Found issues while parsing the following yeasts :")
        for yeast in error_yeasts :
            print("Yeast : {} , {}".format(yeast.name, yeast.brand))

    print("Successfully scraped rolling beers website !")
    return 0



def test_spread_accross_threads() -> int :
    rc = 0
    success = True
    yeasts : list[Yeast] = []

    # Generate fake ids
    for i in range(0,3) :
        for j in range(0,2) :
            yeast = Yeast()
            yeast.name = str(i*2 + j)
            yeasts.append(yeast)

    # Build the thread payload matrix
    matrix = spread_load_accross_threads(5, yeasts)

    success &= len(matrix) == 6
    success &= (len(matrix[0]) == 2)
    success &= (len(matrix[1]) == 1)
    success &= (len(matrix[2]) == 1)
    success &= (len(matrix[3]) == 1)
    success &= (len(matrix[4]) == 1)
    success &= (len(matrix[5]) == 1)

    if not success :
        rc = 1

    return rc


def run_tests() -> int :
    rc = 0
    test_list = [
        test_spread_accross_threads
    ]

    # Run all tests
    for test in test_list :
        rc |= test()

    return rc



if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test" :
        exit(run_tests())
    else :
        returnedcode = main(sys.argv)
        exit(returnedcode)


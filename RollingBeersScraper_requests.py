#!/bin/python3

# https://elitedatascience.com/python-web-scraping-libraries
import requests
from bs4 import BeautifulSoup
import re
import json
from json import JSONEncoder
import sys

class Brand :
    def __init__(self, name, pattern, regex : bool):
        self.name = name
        self.pattern = pattern
        self.regex = regex

    def match(self, brand):
        if self.regex:
            pattern = re.compile(self.pattern)
            match = re.search(pattern, brand)
            if match is not None :
                return True

            # Last chance to get the brand right (sometimes it is not encoded using the brand's regular
            # naming convention, so we have to fallback on this test to get it right !)
            elif brand.upper().find(self.name.upper()) != -1:
                return True
        else :
            if brand.upper().find(self.pattern.upper()) != -1 :
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

def remove_latin_escaped(string:str):
    return string.replace(u'\xa0', u' ')

class Yeast :
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
            'abv' :  re.compile(r"[\D]*([0-9]+%).*"),
            'attenuation' :  re.compile(r".*([0-9]{2})-([0-9]{2}).*"),
            'temperature' :  re.compile(r".*([0-9]{2})-([0-9]{2}).*"),
            'floculation' :  re.compile(r"(.*)")
        }

    def get_dict(self):
        out = self.__dict__.copy()
        out.pop('patterns')
        return out

    def format_data(self):
        # Find Brand from name
        for brand in brands:
            if brand.match(self.name):
                self.brand = brand.name
                break

        # Extract ABV
        self.abv_tol = remove_latin_escaped(self.abv_tol)
        match = re.search(self.patterns['abv'], self.abv_tol)
        if match is not None :
            self.abv_tol = match[1]

        # Extract attenuation
        self.attenuation_range[0] = remove_latin_escaped(self.attenuation_range[0])
        match = re.search(self.patterns['attenuation'], self.attenuation_range[0])
        if match is not None :
            self.attenuation_range[0] = match[1] + u'%'
            self.attenuation_range[1] = match[2] + u'%'

        # Extract floculation
        self.floculation = remove_latin_escaped(self.floculation)
        match = re.search(self.patterns['floculation'], self.floculation)
        if match is not None :
            self.floculation = match[1]

        # Extract temperature range
        self.temp_range[0] = remove_latin_escaped(self.temp_range[0])
        match = re.search(self.patterns['temperature'], self.temp_range[0])
        if match is not None :
            self.temp_range[0] = match[1] + u'°C'
            self.temp_range[1] = match[2] + u'°C'

        # Format price
        if self.price.find('€') == -1 :
            self.price += u'€'

        #https://stackoverflow.com/questions/10993612/how-to-remove-xa0-from-string-in-python
        self.description = self.description.replace(u'\xa0', u' ')
        self.description = self.description.replace('\\', '')

    class YeastEncoder(JSONEncoder):
        def default(self, o):
            outdict = {
                'name' : o.name,
                'brand' : o.brand,
                'link' : o.link,
                'abv' : o.abv_tol,
                'floculation' : o.floculation,
                'attenuation' : [
                    o.attenuation_range[0],
                    o.attenuation_range[1]
                ],
                'price' : o.price,
                'temperature': [
                    o.temp_range[0],
                    o.temp_range[1]
                ],
                'description' : o.description
            }
            return outdict


class NotAYeastError(Exception):
    def __init__(self, link):
        self.link = link


# Finds all available yeasts with their names and links to their description page
def parse_page(page_link, yeasts : list) :
    page = requests.get(page_link)
    contents = page.content
    soup = BeautifulSoup(contents, 'html.parser')

    for elem in soup.find_all('div', href=False, attrs={'class' : 'kl-title-aff'}) :
        yeast = Yeast()
        yeast_block = elem.find('a', href=True)
        yeast.name = yeast_block.find('h3', attrs={'itemprop' : 'name'}).contents[0]
        yeast.link = yeast_block.attrs['href']
        yeasts.append(yeast)

    next_page = soup.find('a', attrs={'class' : 'page-link'}, href=True, string='Suivant')
    if next_page != None :
        return next_page.attrs['href']

    return ''

def parse_yeast(yeast : Yeast) :
    page = requests.get(yeast.link)
    contents = page.content
    soup = BeautifulSoup(contents, 'html.parser')
    price_div = soup.find('div', attrs={'class':'current-price'})
    try:
        price_span = price_div.find('span', attrs={'itemprop' : 'price'})
        yeast.price = price_span.attrs['content']
    except AttributeError:
        yeast.price = 'No data'

    name_field = soup.find('h1', attrs={'itemprop' : 'name'})
    yeast.name = name_field.next
    description_section = soup.find('section', attrs={'class' : 'kl-bg-grey'})
    if description_section is None :
        raise NotAYeastError(yeast.link)

    all_p_blocks = description_section.find_all('p')
    # Shitty code because all yeasts are not all displayed the same way
    description_block = all_p_blocks[1] if (len(all_p_blocks) > 1) else all_p_blocks[0]
    yeast.description = description_block.next

    floculation =  description_section.find('strong', string=re.compile("Floculation.*"))
    attenuation = description_section.find('strong', string=re.compile("Atténuation.*"))
    temperature = description_section.find('strong', string=re.compile("Gamme de Température.*"))
    abv = description_section.find('strong', string=re.compile("Tolerance d'alcool.*"))

    try :
        yeast.floculation = floculation.nextSibling
    except (AttributeError) :
        yeast.floculation = "NA"
    try :
        yeast.attenuation_range[0] = attenuation.nextSibling
    except (AttributeError) :
        yeast.attenuation_range[0] = "NA"
        yeast.attenuation_range[1] = "NA"

    try :
        yeast.temp_range[0] = temperature.nextSibling
    except (AttributeError) :
        yeast.temp_range[0] = "NA"
        yeast.temp_range[1] = "NA"

    try :
        yeast.abv_tol = abv.nextSibling
    except (AttributeError) :
        yeast.abv_tol = "NA"

    return yeast


def parse_args(args):
    out = {}
    for arg in args[1:] :
        if arg == "-j" or arg == "--json" :
            out['json'] = True
    return out

def removed_mislabled_yeasts(yeasts_collection : list, mislabled_yeasts : list):
    out_yeasts = []
    for yeast in yeasts_collection :
        mislabled_found = False
        for mislabled in mislabled_yeasts :
            if yeast.name == mislabled.name :
                mislabled_found = True
                break
        if not mislabled_found :
            out_yeasts.append(yeast)
    return out_yeasts

def main(args):
    parsed_args = parse_args(args)
    yeasts = list()

    # Use the pagination item to loop until reaching the end of the catalogue
    # then use each prerecorded link to isolate data from each yeast (abv, floculation, etc...)
    link = "https://www.rolling-beers.fr/fr/55-toutes-les-liquides"
    while link != '' :
        link = parse_page(link, yeasts)

    mislabled_yeasts = []
    for yeast in yeasts :
        try:
            yeast = parse_yeast(yeast)
            yeast.format_data()
        except NotAYeastError:
            mislabled_yeasts.append(yeast)

    yeasts = removed_mislabled_yeasts(yeasts, mislabled_yeasts)

    if 'json' in parsed_args.keys() and parsed_args['json'] == True :
        content = json.dumps([ob.get_dict() for ob in yeasts], indent=4, ensure_ascii=False)
        with open('yeasts.json','w') as file :
            file.writelines(content)

if __name__ == "__main__" :
    main(sys.argv)


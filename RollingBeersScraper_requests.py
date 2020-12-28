#!/bin/python3

# https://elitedatascience.com/python-web-scraping-libraries
import requests
from bs4 import BeautifulSoup

class Yeast :
    def __init__(self):
        self.name = 'Generic yeast'
        self.link = ''
        self.abv_tol = ''
        self.floculation = '50%'
        self.attenuation = '60%'
        self.price = '0.00€'
        self.temp_range = ''

yeasts = list()


# Finds all available yeasts with their names and links to their description page
def parse_page(page_link) :
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
    price_span = price_div.find('span', attrs={'itemprop' : 'price'})
    yeast.price = price_span.attrs['content']

    yeast.floculation = soup.find('strong', string="Floculation :").nextSibling
    yeast.attenuation = soup.find('strong', string="Atténuation :").nextSibling
    yeast.temp_range = soup.find('strong', string="Gamme de Température :").nextSibling
    yeast.abv_tol = soup.find('strong', string="Tolerance d'alcool :").nextSibling

    return yeast


# Use the pagination item to loop until reaching the end of the catalogue
# then use each prerecorded link to isolate data from each yeast (abv, floculation, etc...)
link = "https://www.rolling-beers.fr/fr/55-toutes-les-liquides"
while link != '' :
    link = parse_page(link)

for yeast in  yeasts :
    yeast = parse_yeast(yeast)


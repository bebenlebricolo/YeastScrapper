#!/bin/python3

#https://www.edureka.co/blog/web-scraping-with-python/

from selenium import webdriver
from bs4 import BeautifulSoup
import pandas as pd


driver = webdriver.Firefox()
driver.get("https://www.rolling-beers.fr/fr/55-toutes-les-liquides")
content = driver.page_source
soup = BeautifulSoup(content)

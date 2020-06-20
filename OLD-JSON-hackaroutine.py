import numpy as np
# import pandas as pd
import re
import time
import pickle
# from glob import glob
# from string import punctuation
from collections import Counter, OrderedDict

from requests_html import HTMLSession

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors


class OrderedCounter(Counter, OrderedDict):
    # no additional code is needed to combine these objects
    # https://stackoverflow.com/a/35448557
    pass


class Cosmetic(HTMLSession):
    '''
    Parent class for organizing Products and Ingredients from CosDNA.com.
    Not intended to be used on its own.
    Assumes the CosDNA URL is valid when forming
    '''

    domain = 'https://cosdna.com'

    with open('./data/ingredients.json', 'rb') as handle:
        INGREDIENTS = json.load(handle)


    sort_dict = {
        'latest': '&sort=date',
        'featured': '&sort=featured',
        'clicks': '&sort=click',
        'reviews': '&sort=review'
    }

    _urls = {
        'i': {
            'base': 'https://cosdna.com/eng/',
            'search': 'https://cosdna.com/eng/stuff.php?q='
        },
        'p': {
            'base': 'https://cosdna.com/eng/cosmetic_',
            'search': 'https://cosdna.com/eng/product.php?q='
    }

    def __init__(self, name=None, cosdna_id=None):
        self._name = name
        self.cosdna_id = cosdna_id

    def link(self, sort=None, cosdna_url=None, _base_url=None):
        '''
        Updates self._cosdna_url if cosdna_url is valid.
        If cosdna_url blank, checks if self._cosdna_url is valid
        If self._cosdna_url blank, searches for CosDNA URL
        '''
        if cosdna_url:
            self._set_cosdna_url(cosdna_url)
        elif not self.cosdna_url:
            self._search(sort=sort, _base_url=_base_url)

    def sync(self):
        self._r = self.get(self.cosdna_url)
        # more actions defined in child classes

    @staticmethod
    def clean(string):
        # https://towardsdatascience.com/fuzzy-matching-at-scale-84f2bfd0c536
        string = string.encode("ascii", errors="ignore").decode()
        string = string.lower()
        chars = [")", "(", ".", "|", "[", "]", "{", "}", "'", '"', "?", "!"]
        esc = '[' + re.escape(''.join(chars)) + ']'
        string = re.sub(esc, '', string)
        string = string.replace('&', 'and')
        string = string.replace(',', ' ')
        string = string.replace('-', ' ')
        string = re.sub(' +',' ',string).strip()
        return string

    # @staticmethod
    # # https://stackoverflow.com/a/28860508
    # def (d, k, v):
    #     try:
    #         var1 = d[k]
    #     except KeyError:
    #         pass


class Product(Cosmetic):

    _stop_words = [
        'cleanser',
        'cream',
        'lotion',
        'mask',
        'masque',
        'moisturizer',
        'serum',
        'sunblock',
        'sunscreen',
        'toner'
    ]

    def __init__(self, name=None, cosdna_id=None, brand=None, product=None):
        super().__init__(self.name, cosdna_id)
        self.brand = brand
        self.product = product

    def link(self, sort='featured', cosdna_url=None):
        '''
        Links Product() to cosdna_url

        Parameters
        ----------
        sort : str, default 'featured'
            Selects the search parameters to use:
            - None (the default sort option on CosDNA)
            - 'latest' : most recent entries first
            - 'featured': seems to be a weighted average of 'latest' and
                    'clicks'
            - 'clicks' : most visited entries first
            - 'reviews' : most reviews first
        cosdna_url : str, default None
            CosDNA URL of ingredient
            If cosdna_url is None, searches for cosdna_url using name
        '''
        super().link(self.name)

    def sync(self, deep=False, sleep=0.5):
        super().sync()
        self._set_name_brand_product(self.name)
        self._set_ingredients(deep=deep, sleep=sleep)
        return self

    def _set_name_brand_product(self, name):
        """
        Helper function for self.sync()
        Returns the brand name and product name of the product as they appear
        in the linked URL
        """
        brand = super().clean(
            self._r.html.find('.brand-name', first=True).text
        )
        product = super().clean(
            self._r.html.find('.prod-name', first=True).text
        )
        if brand:
            self.cosdna_brand, self.cosdna_product = brand, product
        self.cosdna_name = (brand + ' ' + product).strip()

    def _set_ingredients(self, deep=False, sleep=0.5):
        '''
        Helper function for self.sync()
        self.sync() > self._get_ingredients()

        Returns a list of ingredients in the product as Ingredient()

        Parameters
        ----------
        deep : bool, default False
            Calls Ingredient.sync() on every ingredient in the routine
        '''
        table = self._r.html.find('.tr-i')
        self._ings = {}
        self._missing_ings = []
        for row in table:
            cells = row.find('td')
            sub_dict = {}
            if len(cells) == 5:
                # ingredient, function, acne, irritant, safety
                ing, _, _, _, _ = cells
                ing_name = super().clean(ing.text)
                ing_url = (
                    Cosmetic.domain + ing.xpath('//a/@href', first=True)
                )
                ing_id = re.findall("eng/(.*).html", ing_url)[0]
                sub_dict['name'] = ing_name
                # add function, acne, irritant, safety
                # if deep, sync with ingredient page too and sleep
                self._ings[ing_id] = sub_dict
            else:
                ing = cells[0]
                ing_name = ing.find('.text-muted', first=True).text.strip() \
                              .lower()
                self._missing_ings.append(ing_name)
        return self

    @property
    def cosdna_url(self):
        return Cosmetic._urls['prod']['base'] + self.cosdna_id + '.html'

    @property
    def name(self):
        if self.brand and self.product:
            return self.clean(self.brand) + ' ' + self.clean(self.product)
        else:
            return self._name

    @property
    def ingredients(self):
        return [ing['name'] for ing in self._ings]



class Routine(HTMLSession):

    def __init__(self, name=None, routine=None):
        self.name = name
        self.products = []
        if routine:
            self.add(routine)

    def add(self, routine):
        routine = np.array([routine])
        routine = routine.ravel()
        routine = [prod for prod in routine if len(prod) > 1]
        self._routine = routine
        return self

    def sync(self, sort='featured', force=False, deep=False, sleep=0.5):
        for prod in self._routine:

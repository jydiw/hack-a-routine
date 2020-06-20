import numpy as np
import re
import json
import time
# import pickle
# from glob import glob
# from string import punctuation
from collections import Counter, OrderedDict

# import requests
from requests_html import HTMLSession

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors


class OrderedCounter(Counter, OrderedDict):
    # no additional code is needed to combine these objects
    pass

class CosDNA(HTMLSession):

    domain = 'https://cosdna.com'

    def __init__(self, name, cosdna_url=None):
        super().__init__()
        self._name = name
        self.cosdna_url = cosdna_url

    def sync(self, force=False):
        # CODE GOES HERE: check if json exists before syncing
        self._r = self.get(self.cosdna_url)
        return self

    @staticmethod
    def clean(string):
        string = string.encode("ascii", errors="ignore").decode()
        string = string.lower()
        chars_to_remove = [")", "(", ".", "|", "[", "]", "{", "}", "'", '"',
                        "?", "!"]
        rx = '[' + re.escape(''.join(chars_to_remove)) + ']'
        string = re.sub(rx, '', string)
        string = string.replace('&', 'and')
        string = string.replace(',', ' ')
        string = string.replace('-', ' ')
        string = re.sub(' +',' ',string).strip()
        return string

    @staticmethod
    def cosdna_id(url):
        '''
        Returns a unique ingredient identifier based on the URL

        Aliases of the same ingredient point to the same URL in the CosDNA
        database. In the absence of our own relational database, we rely on
        this identifier to collapse multiple aliases into a single entry,
        allowing us to:
        - collapse aliases together when analyzing routines
        - search for aliases'''
        try:
            if 'cosmetic' in url:
                return 'p_' + re.findall("eng/[cosmetic]*_*(.*).html", url)[0]
            elif url:
                return 'i_' + re.findall("eng/(.*).html", url)[0]
        except:
            return 'unavailable'


class Ingredient(CosDNA):

    def __init__(self, name, cosdna_url=None, cas_no=None):
        super().__init__(name=name, cosdna_url=cosdna_url)
        self.cas_no = cas_no

    def sync(self):
        super().sync()      # goes to self.cosdna_url



class Product(CosDNA):

    def __init__(self, name, cosdna_url=None, brand=None, product=None):
        self._name = name
        self.cosdna_url = cosdna_url
        self.brand = brand
        self.product = product

    @property
    def name(self):
        if self.brand is None and self.product is None:
            return self._name
        else:
            self._name = self.brand + ' ' + self.product
            return self._name

    def sync(self, force=False):
        # CODE GOES HERE: check if json exists before syncing
        self._set_name_brand_prod()
        self._ing_ids = self._set_ings(deep=deep, sleep=sleep)
        self._synced = True
        return self

    def _set_name_brand_prod(self):
        self.cosdna_brand = self._r.html.find('.brand-name',
                                              first=True).text.lower()
        self.cosdna_prod = self._r.html.find('.prod-name',
                                             first=True).text.lower()
        with (self.cosdna_brand + ' ' + self.cosdna_prod) as cosdna_name:
            self.cosdna_name = re.sub('\s+', ' ', cosdna_name.strip())

    def _set_ings(self):
        ing_ids = []
        table = self._r.html.find('.tr-i')
        # not sure if this improves performance. idea taken from scikit-learn
        ing_ids_append = ing_ids.append
        for row in table:
            cells = row.find('td')
            if len(cells) == 5:
                # ingredient, function, acne, irritant, safety
                ing_cell, _, _, _, _ = cells
                ing_name = ing_cell.text.strip().lower()
                ing_url = CosDNA.domain + ing_cell.xpath('//a/@href', first=True)
                # function = self._get_function_info(fun)
                ing_id = self.cosdna_url(ing_url)
            else:
                ing = cells[0]
                ing_name = ing.find('.text-muted', first=True).text \
                              .strip().lower()
                ingredient = Ingredient(name=ing_name)
            ingredients_append(ingredient)
        self.ingredients = ingredients


class Cosmetic():
    '''
    Parent class for connecting to CosDNA.com database.
    Not intended to be used on its own.
    '''

    _domain = 'https://cosdna.com'

    _product_stop_words = [
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

    _sort_dict = {
        'latest': '&sort=date',
        'featured': '&sort=featured',
        'clicks': '&sort=click',
        'reviews': '&sort=review'
    }

    _search_dict = {
        'ingredient': 'https://cosdna.com/eng/stuff.php?q=',
        'product': 'https://cosdna.com/eng/product.php?q='
    }

    _base_dict = {
        'ingredient': 'https://cosdna.com/eng/',
        'product': 'https://cosdna.com/eng/cosmetic_'
    }

    def __init__(self):
        super().__init__()
        self._skip = False

    def link(self, cosdna_url=None, cosdna_id=None, type=None):
        '''
        Links Cosmetic with CosDNA URL.
        If CosDNA URL is unknown, calls _search() with self._query
        '''
        if cosdna_id:
            self._cosdna_url = _check_url(id=cosdna_id)
            if self._cosdna_url:

            self._cosdna_url = self._check_url(cosdna_url)
                # do not search if there is a valid cosdna_url

    def _check_url(self, url=None, id=None, type=None):
        '''
        Checks if url is in the CosDNA domain.

        Parameters
        ----------
        url : str
            the web address to check
        '''
        if id:
            url = Cosmetic._base_dict[type] + id + '.html'
        if url:
            if Cosmetic._domain in url:
                return url
            else:
                print('Invalid CosDNA URL')
                return None
        else:
            print('Empty URL')
            return None


    def search(self, query=None, sort=None, type=None, auto=True):



    def sync(self, query=None, cosdna_url=None, cosdna_id=None, sort=None,
             type=None, _link=True, _search=True, _sync=True)
        '''
        Searches and syncs information with CosDNA.
        '''
        if _link:



class Product(Search):

    _base_url = 'https://cosdna.com/eng/product.php?q='

    def __init__(self, query=None, brand=None, product=None, cosdna_id=None):
        # `name` property will concatenate `brand` and `product`
        self._query  = query
        self._brand = brand
        self._product = product
        self._cosdna_id = cosdna_id
        if self._cosdna_id:
            self._cosdna_url = Product._base_url + self._cosdna_id
        super().__init__(query=self._query, cosdna_url
import re
import time
import json
import unidecode
import numpy as np

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
    '''

    _domain = 'https://cosdna.com'

    _sort_dict = {
        'latest': '&sort=date',
        'featured': '&sort=featured',
        'clicks': '&sort=click',
        'reviews': '&sort=review'
    }

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
        'toner',
        'treatment'
    ]

    # list of common ingredients and their names
    with open('./data/ingredients/ingredient_names.json', 'rb') as handle:
        INGREDIENT_NAMES = json.load(handle)

    def __init__(self, name=None, cosdna_id=None):
        super().__init__()
        self._name = self.clean(name)   # allows for link()
        self.cosdna_id = cosdna_id      # assumed to be valid
        self._skip = False              # breaks sync() loop
        self.synced = False

    def link(self, sort=None, cosdna_url=None):
        '''
        Updates self._cosdna_url if instantiated without CosDNA ID.
        If cosdna_url blank, checks if self._cosdna_url is valid
        If self._cosdna_url blank, searches for CosDNA URL
        '''
        if self.linked:         # checks if self.cosdna_id exists
            pass
        elif not cosdna_url:    # search only if cosdna_url not supplied
            self._search(sort=sort)
        elif self._urls['base'] in cosdna_url:
            self.cosdna_id = self._u2i(cosdna_url)
        return self

    def _search(self, sort=None, _try_stopwords=True):
        ### SEARCHING FOR AN ENTRY IN COSDNA ###
        if self._query and (not self._skip):
            search_url = self._get_search_url(query=self._query, sort=sort)
            self._r = self.get(search_url)
            top = self._r.html.find('td', first=True)
            if top:     # if top result exists, take it
                self._cosdna_url = (
                    Cosmetic._domain + top.xpath('//a/@href', first=True)
                )
                return self
            ### IF THERE ARE NO SEARCH RESULTS ###
            else:
                if _try_stopwords:      # search again removing stopwords
                    for word in self._stop_words:
                        self._query = re.sub('|'.join(self._stop_words),'', query)
                        return self._search(sort=sort, _try_stopwords=False)
                elif self._r.html.find('.text-danger'):     # or try new search
                    print(f'No results for {self._name} on CosDNA.')
                    print("Enter new search (to skip search, enter 'SKIP' w/o quotes):")
                    self._query = input(' ')
                    if self._query == 'SKIP':
                        self._skip = True
                        return self
                    else:
                        return self._search(sort=sort)
                else:
                    self._cosdna_url = self._r.url
                    return self
        else:
            print('Link with valid CosDNA URL or product name to proceed.')
            return self

    def _get_search_url(self, query=None, sort=None):
        '''
        Generates a php search_url directly from query
        '''
        query = self.clean(query, True)
        # _base_url defined in child classes
        # Product() has different sort options, Ingredient() does not
        if sort in [*Cosmetic._sort_dict]:
            search_url = self._urls['search'] + query + Cosmetic._sort_dict[sort]
        else:
            search_url = self._urls['search'] + query
        return search_url

    def sync(self):
        '''
        Sets up scrape from linked url
        Child classes define more actions
        '''
        if self._skip:
            pass
        elif self.cosdna_url:
            self._r = self.get(self.cosdna_url)
            # more actions defined in child classes
        else:
            print('Initialize or link with valid CosDNA URL to proceed')
        return self

    def _u2i(self, url):
        return re.findall("eng/(.*).html", url)[0]

    def _i2u(self, id_):
        return self._urls['base'] + id_ + '.html'

    @staticmethod
    def check(key, dict_):
        # https://stackoverflow.com/a/28860508
        try:
            var1 = dict_[key]
            return True
        except KeyError:
            return False

    @staticmethod
    def clean(string, query=False):
        # https://stackoverflow.com/a/2633310
        string = unidecode.unidecode(string.lower())
        string = re.sub('[\‘\’]', "'", string)
        if query:
            string = re.sub('and|or|not', '', string)
            string = re.sub('\s+','+',string).strip()
        else:
            string = re.sub('&', 'and', string)
            string = re.sub('\s+',' ',string).strip()
        string = re.sub("[^a-z0-9\s\-\+\']", '', string)
        return string

    @property
    def cosdna_url(self):
        if self.cosdna_id:
            return self._i2u(self.cosdna_id)
        else:
            return self._cosdna_url

    # linked and synced defined as properties
    # since Routine() will not share this behavior
    @property
    def linked(self):
        if self.cosdna_id:
            return True
        else:
            return False

    # @property
    # def synced(self):
    #     return self._synced


class Ingredient(Cosmetic):
    '''
    Syncs and stores ingredient information from CosDNA.com.

    Search for ingredients based on name, link to CosDNA page, and scrape
    information to store in instance.

    Parameters
    ----------
    name : str, default None
        Name of ingredient.

    cas_no : str, default None
        CAS Registry Number

    cosdna_url : str, default None
        URL of ingredient in CosDNA database

    >>> i = Ingredient('salicylic acid')
    >>> i.name                                     # returns assigned name
    'salicylic acid'
    >>> i.link_sync()                              # scrapes top result
    >>> i.name                                     # returns CosDNA name
    'bha'

    >>> i.link('https://cosdna.com/eng/0f1b7f1402.html')    # directly update link
    >>> i.sync()
    >>> i.name
    'capryloyl salicylic acid'
    '''

    _urls = {
        'base': 'https://cosdna.com/eng/',
        'search': 'https://cosdna.com/eng/stuff.php?q='
    }

    def __init__(self, name=None, cas_no=None, cosdna_id=None):
        super().__init__(name=name, cosdna_id=cosdna_id)
        self.cas_no = cas_no
        if self.cas_no:     # give search priority to cas_no
            self._query = self.cas_no
        else:
            self._query = self._name

    def link(self, cosdna_url=None):
        '''
        Links Ingredient() to cosdna_url

        Parameters
        ----------
        cosdna_url : str, default None
            CosDNA URL of ingredient
            If cosdna_url is None, searches for cosdna_url using either:
                - cas_no (preferential), or
                - name
        '''
        super().link(cosdna_url=cosdna_url)

    def sync(self):
        '''
        Scrapes information from linked URL
        - name on CosDNA website
        - ingredient aliases
        - molar mass
        - hydro-/lipo-philic balance
        - CAS Registry Number
        - ingredient description

        Visit the following websites for more information:
        - molar mass: <https://en.wikipedia.org/wiki/Molar_mass>
        - HLB: <https://en.wikipedia.org/wiki/Hydrophilic-lipophilic_balance>
        - CAS No.: <https://en.wikipedia.org/wiki/CAS_Registry_Number>
        '''
        super().sync()          # goes to cosdna_url
        if not self._skip:      # grabs ingredient information
            self._cosdna_name, self.aliases = self._get_names()
            self.mass, self.hlb, self.cas_no = self._get_chemical_info()
            self.description = self._r.html.find(
                'div.chem.mb-5 > div.linkb1.ls-2.lh-1', first=True
                ).text
            self.cosdna_id = self._u2i(self._r.url)
            self.synced = True
        return self

    def link_sync(self, cosdna_url=None):
        self.link(cosdna_url=cosdna_url)
        self.sync()
        return self

    def _get_names(self):
        '''
        Helper function for self.sync()
        self.sync() > self._get_names()

        Returns the name and aliases of the ingredient as they appear in the
        linked URL
        '''
        cosdna_name = super().clean(
            self._r.html.find('.text-vampire', first=True)
        )
        aliases = self._r.html.find('div.chem.mb-5 > div.mb-2', first=True)
        aliases = aliases.split(',')
        aliases = [super().clean(a) for a in aliases]
        return cosdna_name, aliases

    def _get_chemical_info(self):
        '''
        Helper function for self.sync()
        self.sync() > self._get_chemical_info()

        Returns the molar mass, hydro-/lipo-philic balance, and CAS Registry
        Number as they appear in the linked URL
        '''
        mass, hlb, cas_no = None, None, None
        ci = self._r.html                                                \
                 .find('div.d-flex.justify-content-between', first=True) \
                 .text.lower()
        if 'molecular weight' in ci:
            try:
                mass = float(re.findall(".*weight[^\d\.]+(\d+\.\d+).*", ci)[0])
            except:
                mass = None
        if 'hlb' in ci:
            try:
                hlb = float(re.findall(".*hlb[^\d\.]+(\d+\.\d+).*", ci)[0])
            except:
                hlb = None
        if 'cas no' in ci:
            cas_no = re.findall(".*cas no[^\d\-]+(\d+\-\d+\-\d+).*", ci)[0]
        return mass, hlb, cas_no

    @property
    def name(self):
        if self.synced:
            try:
                n = super().INGREDIENT_NAMES[self.cosdna_id]['name']
                return n
            except KeyError:
                return self._cosdna_name
        elif self._skip:
            return 'SKIP: ' + self._name
        else:
            return self._name

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"""Ingredient(
    name='{self.name}',
    cas_no='{self.cas_no}',
    cosdna_id='{self.cosdna_id}'
)
"""


class Product(Cosmetic):
    '''
    Syncs and stores product information from CosDNA.com.

    Search for products based on name, link to CosDNA page, and scrape
    information to store in instance.

    Parameters
    ----------
    name : str, default None
        Name of ingredient.

    brand : str, default None
        Name of brand. Does not affect search--purely for internal purposes.

    product : str, default None
        Name of product. Does not affect search--purely for internal purposes.

    cosdna_url : str, default None
        URL of ingredient in CosDNA database
    '''

    _urls = {
        'base': 'https://cosdna.com/eng/cosmetic_',
        'search': 'https://cosdna.com/eng/product.php?q='
    }

    def __init__(self, name=None, brand=None, product=None, cosdna_id=None):
        # initialize using 'name' property
        self.brand = brand
        self.product = product
        if brand and product:
            super().__init__(name=self.name, cosdna_id=cosdna_id)
        else:
            super().__init__(name=name, cosdna_id=cosdna_id)
        self._query = self._name

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
        return super().link(sort=sort, cosdna_url=cosdna_url)

    def sync(self):
        '''
        Scrapes information from linked URL
        - brand name
        - product name
        - ingredient names and corresponding URLs
        Saves ingredients as Ingredient()

        Parameters
        ----------
        deep : bool, default False
            Calls Ingredient.sync() on every ingredient in the routine
        '''
        super().sync()
        if self._skip:
            self._ingredients = []
            return self
        else:
            self.cosdna_id = self._u2i(self._r.url).replace('cosmetic_', '')
            self._set_name_brand_product()
            self._set_ingredients()
            self.synced = True
            return self

    def link_sync(self, sort='featured', cosdna_url=None):
        self.link(sort=sort, cosdna_url=cosdna_url)
        self.sync()

    def _set_name_brand_product(self):
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

    def _set_ingredients(self):
        '''
        Helper function for self.sync()
        self.sync() > self._set_ingredients()

        Returns a list of ingredients in the product as Ingredient()

        Parameters
        ----------
        deep : bool, default False
            Calls Ingredient.sync() on every ingredient in the routine
        '''
        table = self._r.html.find('.tr-i')
        self._ings = []             # list of Ingredient() objects
        self._missing_ings = []     # list of strings
        for row in table:
            cells = row.find('td')
            sub_dict = {}
            if len(cells) == 5:
                # ingredient, function, acne, irritant, safety
                ing, _, _, _, _ = cells
                ing_name = super().clean(ing.text)
                ing_url = (
                    Cosmetic._domain + ing.xpath('//a/@href', first=True)
                )
                ing_id = re.findall("eng/(.*).html", ing_url)[0]

                ingredient = Ingredient(name=ing_name, cosdna_id=ing_id)
                # add function, acne, irritant, safety
                # if deep, sync with ingredient page too and sleep
                self._ings.append(ingredient)
            else:
                ing = cells[0]
                ing_name = ing.find('.text-muted', first=True).text.strip() \
                              .lower()
                self._missing_ings.append(ing_name)
        return self

    # def _get_function_info(self, fun):
    #     function = fun.text.strip().lower().split(',')
    #     if 'sunscreen' in function:
    #         try:
    #             uva = re.search("uv[ab]\d",
    #                             fun.xpath('//img')[0].attrs['src'])[0]
    #             uvb = re.search("uv[ab]\d",
    #                             fun.xpath('//img')[1].attrs['src'])[0]
    #             function.append(uva)
    #             function.append(uvb)
    #         except:
    #             pass
    #     return function

    @property
    def name(self):
        if self.brand is None and self.product is None:
            return self._name
        else:
            self._name = self.brand + ' ' + self.product
            return self._name

    @property
    def ingredients(self):
        return [ing.name for ing in self._ings]

    @property
    def cosdna_urls(self):
        return [super()._i2u(ing) for ing in [*self._ings]]

    @property
    def ing_ids(self):
        return [ing.cosdna_id for ing in self._ings]

    @property
    def ing_dict(self):
        for ing in self.ing_ids


    @property
    def product_dict(self):
        cid = self.cosdna_id
        brand = self.brand
        ings = self.ing_ids
        name = self.name
        prod = self.product
        return dict([
            (cid, dict([
                ('brand', brand),
                ('ingredients', ings),
                ('name', name),
                ('product', prod)
                ])
            )
        ])

    # def __str__(self):
    #     return f'{self.name}\n\n{self.ingredients}'
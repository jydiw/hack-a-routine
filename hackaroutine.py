import numpy as np
import pandas as pd
import re
import time
import pickle
# from glob import glob
# from string import punctuation
from collections import Counter, OrderedDict

import requests
from requests_html import HTMLSession


class OrderedCounter(Counter, OrderedDict):
    pass


class CosDNA(HTMLSession):
    '''
    Parent class for connecting to CosDNA.com database.
    Not intended to be used on its own.
    '''

    base_url = 'https://cosdna.com'

    sort_dict = {
        'latest': '&sort=date',
        'featured': '&sort=featured',
        'clicks': '&sort=click',
        'reviews': '&sort=review'
    }
    
    with open('./data/master_dict.pickle', 'rb') as handle:
        master_dict = pickle.load(handle)

    def __init__(self, name=None):
        super().__init__()
        self._name = name
        self._synced = False    # synced in child classes


class Cosmetic(CosDNA):
    '''
    Parent class for organizing Products and Ingredients from CosDNA.com.
    Not intended to be used on its own.
    '''
    
    stop_words = [
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
    
    
    def __init__(self, name=None, cosdna_url=None):
        super().__init__(name)
        self._cosdna_url = cosdna_url

    def link(self, sort=None, cosdna_url=None, _base_url=None):
        '''
        Checks if self._cosdna_url is valid
        then links to self._cosdna_url
        '''
        self._cosdna_url = self._check_url(cosdna_url)
        if self._cosdna_url:
            return self
        else:
            self._search(sort, self._query, _base_url)

    def _search(self, query, sort=None, _base_url=None):
        '''
        self.link() > _search()
        Makes a GET request to search_url
        Child classes define more actions
        '''
        if query == 'SKIP':
            self._name = 'SKIP: ' + self._name
            print(f'{self._name}')
            return self
        elif query:
            search_url = self._get_search_url(sort, self._query, _base_url)
            self._r = self.get(search_url)
            top = self._r.html.find('td', first=True)   # top result
            if top:
                self._cosdna_url = (CosDNA.base_url
                                    + top.xpath('//a/@href', first=True))
                return self
            else:
#                 temp_query = self._query.split(' ')
#                 temp_query = ' '.join([w for w in temp_query if w not in Cosmetic.stop_words])
#                 temp_search_url = self._get_search_url(sort, temp_query, _base_url)
                # no result
                nr = self._r.html.find('.text-danger')
                if nr:
                    print(f'No results for {self._query} on CosDNA.')
                    print('Enter new search (to skip search, enter 'SKIP' w/o quotes):')
                    name = input('')
                    self._query = name
                    return self._search(sort, _base_url)
                else:
                    self._cosdna_url = self._r.url
                    return self
        else:
            print('Link with valid CosDNA URL or product name to proceed.')
            return self

    def _get_search_url(self, query, sort=None, _base_url=None):
        '''
        self.link() > _search() > _get_search_url()
        Generates a php search_url directly from query
        Child classes define _base_url
        '''
        query = re.sub('[^a-z0-9\s\-\']', '', query.lower())
        query = re.sub('([a-z])\-([a-z])', r'\1 \2', query)
        query = query.replace(' ', '+')
        # _base_url defined in child classes
        # Product() has different sort options, Ingredient() does not
        if sort in [*CosDNA.sort_dict]:
            search_url = _base_url + query + CosDNA.sort_dict[sort]
        else:
            search_url = _base_url + query
        return search_url

    def sync(self):
        '''
        Sets up scrape from linked url
        Child classes define more actions
        '''
        if self.cosdna_url:
            # child classes define more actions
            self._r = self.get(self.cosdna_url)
            return self
        else:
            print('Initialize or link with valid CosDNA URL to proceed')
            return self

    def _check_url(self, url=None):
        '''
        Checks if url is in the CosDNA domain.

        Parameters
        ----------
        url : str
            the web address to check'''
        if not url:
            if not self._cosdna_url:
                return None
            else:
                return self._cosdna_url
        elif CosDNA.base_url in url:
            return url
        else:
            print('Invalid CosDNA URL.')
            return None

    @property
    def cosdna_url(self):
        return self._check_url(self._cosdna_url)

    @property
    def linked(self):
        if self.cosdna_url:
            return True
        else:
            return False

    @property
    # defined as a property since Routine() will not share this behavior
    def synced(self):
        return self._synced


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

    def __init__(self, name=None, cas_no=None, cosdna_url=None):
        self.cas_no, self._cosdna_id = cas_no, None
        super().__init__(name, cosdna_url)

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
        if self.cas_no:
            self._query = self.cas_no
        else:
            self._query = self._name
        return super().link(sort=None, cosdna_url=cosdna_url,
                            _base_url='https://cosdna.com/eng/stuff.php?q=')

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
        super().sync()     # goes to cosdna_url
        self._cosdna_name, self.aliases = self._get_names()
        self.mass, self.hlb, self.cas_no = self._get_chemical_info()
        self.description = self._get_description()
        self._synced = True
        return self

    def link_sync(self, cosdna_url=None):
        self.link(cosdna_url)
        self.sync()
        return self

    def _get_names(self):
        '''
        Helper function for self.sync()
        self.sync() > self._get_names()

        Returns the name and aliases of the ingredient as they appear in the
        linked URL
        '''
        cosdna_name = self._r.html.find('.text-vampire', first=True) \
                          .text.lower()
        aliases = self._r.html.find('div.chem.mb-5 > div.mb-2', first=True) \
                      .text.lower().split(', ')
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
                 .text
        if 'Molecular Weight' in ci:
            try:
                mass = float(re.findall(".*Weight[^\d\.]+(\d+\.\d+).*", ci)[0])
            except:
                mass = None
        if 'HLB' in ci:
            try:
                hlb = float(re.findall(".*HLB[^\d\.]+(\d+\.\d+).*", ci)[0])
            except:
                hlb = None
        if 'Cas No' in ci:
            cas_no = re.findall(".*Cas No[^\d\-]+(\d+\-\d+\-\d+).*", ci)[0]
        return mass, hlb, cas_no

    def _get_description(self):
        '''
        Helper function for self.sync()
        self.sync() > self._get_description()

        Returns the description of the ingredient as it appears in the linked
        URL
        '''
        return self._r.html                                                  \
                   .find('div.chem.mb-5 > div.linkb1.ls-2.lh-1', first=True) \
                   .text

    @property
    def name(self):
        if self.synced:
            return self._cosdna_name
        else:
            return self._name

    @property
    def cosdna_id(self):
        '''
        Returns a unique ingredient identifier based on the URL

        Aliases of the same ingredient point to the same URL in the CosDNA
        database. In the absence of our own relational database, we rely on
        this identifier to collapse multiple aliases into a single entry,
        allowing us to:
        - collapse aliases together when analyzing routines
        - search for aliases
        '''
        if not self._cosdna_id:
            if self.cosdna_url:
                self._cosdna_id = re.findall(
                    "eng/(.*).html", self.cosdna_url)[0]
            else:
                self._cosdna_id = 'unavailable'
        return self._cosdna_id

    def __str__(self):
        return self.name


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

    def __init__(self, name=None, brand=None, product=None, cosdna_url=None):
        self._name, self.brand, self.product = name, brand, product
        # initialize using 'name' property
        super().__init__(self.name, cosdna_url)

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
        self._query = self.name
        return super().link(sort=sort, cosdna_url=cosdna_url,
                            _base_url='https://cosdna.com/eng/product.php?q=')

    def sync(self, deep=False):
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
        if self._query == 'SKIP':
            self._ingredients = []
            return self
        else:
            super().sync()
            self._set_name_brand_product(self._query)
            self._ingredients = self._get_ingredients(deep)
            self._synced = True
            return self

    def link_sync(self, sort='featured', cosdna_url=None, deep=False):
        self.link(sort=sort, cosdna_url=cosdna_url)
        self.sync(deep=deep)

    def _set_name_brand_product(self, name):
        '''
        Helper function for self.sync()
        self.sync() > self._set_name_brand_product()

        Returns the brand name and product name of the product as they appear
        in the linked URL
        '''
        cosdna_brand = self._r.html.find('.brand-name', first=True).text.lower()
        cosdna_product = self._r.html.find('.prod-name', first=True).text.lower()
        cosdna_name = str(cosdna_brand + ' ' + cosdna_product).strip()
        if cosdna_brand:
            self.brand, self.product = cosdna_brand, cosdna_product
        else:
            self._name = name

    def _get_ingredients(self, deep):
        '''
        Helper function for self.sync()
        self.sync() > self._get_ingredients()

        Returns a list of ingredients in the product as Ingredient()

        Parameters
        ----------
        deep : bool, default False
            Calls Ingredient.sync() on every ingredient in the routine
        '''
        ingredients = []
        table = self._r.html.find('.tr-i')
        # not sure if this improves performance. idea taken from scikit-learn
        ingredients_append = ingredients.append
        for row in table:
            cells = row.find('td')
            if len(cells) == 5:
                # ingredient, function, acne, irritant, safety
                ing, _, _, _, _ = cells
                ing_name = ing.text.strip().lower()
                ing_url = (Cosmetic.base_url
                           + ing.xpath('//a/@href', first=True))
                # function = self._get_function_info(fun)
                ingredient = Ingredient(name=ing_name,
                                        cosdna_url=ing_url)
                if deep:
                    ingredient.sync()
                    time.sleep(0.5)
            else:
                ing = cells[0]
                ing_name = ing.find('.text-muted', first=True).text.strip() \
                              .lower()
                ingredient = Ingredient(name=ing_name)
            ingredients_append(ingredient)
        return ingredients

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
        return [ing.name for ing in self._ingredients]

    @property
    def cosdna_urls(self):
        return [ing.cosdna_url for ing in self._ingredients]

    # _cosdna_ids and _ing_dict used for Routine()
    @property
    def _cosdna_ids(self):
        return [ing.cosdna_id for ing in self._ingredients]

    @property
    def _ingredient_dict(self):
        return dict(zip(self._cosdna_ids, self.ingredients))

    def __str__(self):
        return f'{self.name}\n\n{self.ingredients}'


class Routine(CosDNA):
    '''
    Container for Product() and Ingredient() objects.

    Tabulates all ingredients in routine.

    Parameters
    ----------
    name : str, default None
        Name of routine. Optional

    routine : list, default None
        List if products in routine. Products are stored as Product() objects.
    '''

    def __init__(self, name=None, routine=None):
        super().__init__(name)
        self.products = []
        if routine:
            self.add(routine)

    def add(self, routine):
        '''
        Adds products to the routine

        Parameters
        ----------
        routine : list, default None
            List if products in routine. Products are stored as Product()
            objects.
        '''
        routine = np.array([routine])
        routine = routine.ravel()
        for product in routine:
            if type(product) == Product:
                self.products.append(product)
            else:
                self.products.append(Product(product))
        return self

    def link(self, sort='featured', force=False):
        '''
        Calls Product.link() for all products in routine

        Parameters
        ----------
        sort : str, default 'featured'
            Chooses how to sort the search results for each Product()

        force : bool, default False
            Calls Product.link() on Product() even if it has already been
            linked.
        '''
        self.link_sync(sort=sort, force=force, _link=True, _sync=False)

    def sync(self, force=False, deep=False):
        '''
        Calls Product.sync() for all products in routine

        Parameters
        ----------
        force : bool, default False
            Calls Product.sync() on Product() even if it has already been
            synced

        deep : bool, default False
            Calls Ingredient.sync() on every ingredient in the routine
        '''
        self.link_sync(sort=sort, force=force, deep=deep, _link=False,
                       _sync=True)

    def link_sync(self, sort='featured', force=False, deep=False, _link=True,
                  _sync=True):
        '''
        Calls Product.link().sync() for all products in routine
        Tabulates frequency of ingredients across entire routine

        Parameters
        ----------
        force : bool, default False
            Calls Product.sync() on Product() even if it has already been
            synced

        deep : bool, default False
            Calls Ingredient.sync() on every ingredient in the routine
        '''
        for product in self.products:
            if _link:
                if force:
                    product.link(sort)
                else:
                    if not product.linked:
                        product.link(sort)
            if _sync:
                if force:
                    product.sync(deep)
                    changes = True
                else:
                    if not product.synced:
                        product.sync(deep)
                        changes = True
            time.sleep(0.5)
        if changes:
            self._analyze()
        else:
            return self

    def _analyze(self):
        '''
        Helper function for self.sync()
        self.sync() > self._analyze()

        Tabulates frequency of cosdna_ids across all Products
        '''
        self._routine_ids, self._routine_dict = self._get_routine_info()
        self._counts = self._translate_counter(self._routine_dict,
                                               Counter(self._routine_ids))
        self._product_vectors = self._get_product_vectors()
        return self

    def _get_routine_info(self):
        '''
        Helper function for self.sync()
        self.sync() > self._analyze() > self._get_routine_info()

        Creates dictionary to translate cosdna_id to ingredient name
        Creates routine_ids and routine_dict for entire routine
        '''
        routine_ids = []
        routine_dict = {}
        for product in self.products:
            product_dict = product._ingredient_dict
            routine_ids += product._cosdna_ids
            routine_dict.update(product_dict)
        routine_dict.update({'unavailable': 'unavailable'})
        return routine_ids, routine_dict

    def _translate_counter(self, translation_dict, counter):
        '''
        Helper function for self.sync()
        self.sync() > self._analyze() > self._translate_counter()

        Translates Counter() object using routine_dict
        Visit <https://stackoverflow.com/questions/51423217/> for more
        information
        '''
        return OrderedCounter(dict(
            (translation_dict.get(k, k), v) for (k, v) in counter.items()
        ))

    def _get_product_vectors(self):
        '''
        Helper function for self.sync()
        self.sync() > self._analyze() > self._get_product_vectors()

        Generates product vectors in order to quickly assess the presence of
        ingredients in a routine. Over 5x than searching through
        Product._cosdna_ids
        '''
        product_vectors = []
        for product in self.products:
            product_vector = []
            product_vector_append = product_vector.append
            for cosdna_id in self._routine_ids:
                if cosdna_id in product._cosdna_ids:
                    product_vector_append(1)
                else:
                    product_vector_append(0)
            product_vectors.append(product_vector)
        return product_vectors

    def top_ingredients(self, top=None, mask=None):
        '''
        Returns specified number of most common ingredients

        Parameters
        ----------
        top : int, default None
            Specifies number of ingredients to return

        mask : list, default None
            Specifies which ingredients to return
        '''
        if mask:
            mask = [Ingredient(x).link_sync().cosdna_id for x in mask]
            masked_counts = OrderedCounter(
                [x for x in self._routine_ids if x in mask]
            )
            return masked_counts.most_common(top)
        else:
            return self._counts.most_common(top)

    def has(self, ingredient):
        '''
        Returns products which include ingredient

        Parameters
        ----------
        ingredient : str
            Name of ingredient. Works for aliases as long as they are present
            in CosDNA.
        '''
        # add 'AND' / 'OR' functionality!
        ingredient_id = Ingredient(ingredient).link_sync().cosdna_id
        isolated_products = []
        for i, product_vector in enumerate(self._product_vectors):
            try:
                ingredient_index = self._routine_ids.index(ingredient_id)
                if product_vector[ingredient_index] == 1:
                    isolated_products.append(self.products[i].name)
            except:
                print(f'Routine does not have {ingredient}.')
                break
        return isolated_products

    @property
    def routine(self):
        try:
            return [product.name for product in self.products]
        except:
            return self.products

    @property
    def cosdna_urls(self):
        return [product.cosdna_url for product in self.products]

    @property
    def brands(self):
        return [product.brand for product in self.products]

    @property
    def linked(self):
        try:
            return all([product.linked for product in self.products])
        except:
            return False

    @property
    def synced(self):
        try:
            return all([product.synced for product in self.products])
        except:
            return False

    @property
    def ingredients(self):
        return list(set(self._routine_ingredients))

    @property
    def top(self):
        return self.top_ingredients(10)

#     def __str__(self):
#         return f'Routine "{self.name}" with {len(self.routine)} products'

#     def __repr__(self):
#         return f'Routine(name={self.name}, routine={[product.name for product in self.routine]})'

import requests


from Orange import data
from orangecontrib.text import Corpus



import re

#API_URL = 'https://mine-graph.de/api/search'
RATE_LIMIT = False
RATE_LIMIT_MIN_WAIT = None
RATE_LIMIT_LAST_CALL = None



def set_lang(prefix):
    '''
  Change the language of the API being requested.
  Set `prefix` to one of the two letter prefixes found on the `list of all Mines <http://meta.wikimedia.org/wiki/List_of_Wikipedias>`_.

  After setting the language, the cache for ``search``, ``suggest``, and ``summary`` will be cleared.

  .. note:: Make sure you search for page titles in the language that you have set.
  '''
    global API_URL
    API_URL = 'https://mine-graph.de/api/search'

    for cached_func in (search, suggest):
        pass

def search(query, results=10, suggestion=False):
    '''
  Do a Mine search for `query`.

  Keyword arguments:

  * results - the maxmimum number of results returned
  * suggestion - if True, return results and suggestion (if any) in a tuple
  '''

    search_params = {
        'list': 'search',
        'srprop': '',
        'srlimit': results,
        'limit': results,
        'srsearch': query,
        'q': query,
        'a': False,
        'p': 1,
        's': results
    }
    
    raw_results = _wiki_request(search_params)
    if 'error' in raw_results:
        if raw_results['error']['info'] in ('HTTP request timed out.', 'Pool queue is full'):
            raise HTTPTimeoutError(query)
        else:
            raise WikipediaException(raw_results['error']['info'])
    #search_title = (d['_source']['origin']['title'] for d in raw_results['hits']['hits'])
    
    return raw_results
    


def suggest(query):
    '''
  Get a Mine search suggestion for `query`.
  Returns a string or None if no suggestion was found.
  '''

    search_params = {
        'list': 'search',
        'srinfo': 'suggestion',
        'srprop': '',
    }
    search_params['srsearch'] = query

    raw_result = _wiki_request(search_params)

    if raw_result['query'].get('searchinfo'):
        return raw_result['query']['searchinfo']['suggestion']

    return None


def page(title, pageid=None, auto_suggest=True, redirect=True, preload=False):
    '''
  Get a MinePage object for the page with title `title` or the pageid
  `pageid` (mutually exclusive).

  Keyword arguments:

  * title - the title of the page to load
  * pageid - the numeric pageid of the page to load
  * auto_suggest - let MIne find a valid page title for the query
  * redirect - allow redirection without raising RedirectError
  * preload - load content, summary, images, references, and links during initialization
  '''
    title_tmp = title
    auto_suggest = False
    
    if title is not None:
        if auto_suggest:
            results, suggestion = search(title, results=1, suggestion=True)
            try:
                title = suggestion or results[0]
            except IndexError:
                # if there is no suggestion or search results, the page doesn't exist
                raise PageError(title)
        
        return MinePage(title)
  
  
class MinePage(object):
    '''
  Contains data from a Mine page.
  Uses property methods to filter data from the raw HTML.
  '''

    def __init__(self, title, pageid=None, redirect=True, preload=False, original_title=''):
        if title is not None:
            self.title = title
            self.original_title = original_title or title
        else:
            raise ValueError("Either a title or a pageid must be specified")
    
    
    def __eq__(self, other):
        try:
            return (
                    self.pageid == other.pageid
                    and self.title == other.title
                    and self.url == other.url
                    and self.abstract == other.abstract
                )
        except:
            return False

    def __load(self, redirect=True, preload=False):
        '''
    '''
    def __continued_query(self, query_params):
        '''
    Based on https://www.mediawiki.org/wiki/API:Query#Continuing_queries
    '''
        query_params.update(self.__title_query_param)

        last_continue = {}
        prop = query_params.get('prop', None)

        while True:
            params = query_params.copy()
            params.update(last_continue)

            request = _wiki_request(params)

            if 'query' not in request:
                break

            pages = request['query']['pages']
            if 'generator' in query_params:
                for datum in pages.values():  # in python 3.3+: "yield from pages.values()"
                    yield datum
            else:
                for datum in pages[self.pageid][prop]:
                    yield datum

            if 'continue' not in request:
                break

            last_continue = request['continue']


    def html(self):
        '''
    Get full page HTML.

    .. warning:: This can get pretty slow on long pages.
    '''

        if not getattr(self, '_html', False):
            query_params = {
                'prop': 'revisions',
                'rvprop': 'content',
                'rvlimit': 1,
                'rvparse': '',
                'titles': self.title
            }

            request = _wiki_request(query_params)
            self._html = request['query']['pages'][self.pageid]['revisions'][0]['*']

        return self._html

    @property
    def content(self):
        '''
    Plain text content of the page, excluding images, tables, and other data.
    '''

        if not getattr(self, '_content', False):
            query_params = {
                'prop': 'extracts|revisions',
                'explaintext': '',
                'rvprop': 'ids'
            }
            if not getattr(self, 'title', None) is None:
                query_params['titles'] = self.title
            else:
                query_params['pageids'] = self.pageid
            request = _wiki_request(query_params)
        return []

    @property
    def revision_id(self):
        '''
    Revision ID of the page.

    The revision ID is a number that uniquely identifies the current
    version of the page. It can be used to create the permalink or for
    other direct API calls. See `Help:Page history
    <http://en.wikipedia.org/wiki/Wikipedia:Revision>`_ for more
    information.
    '''

        if not getattr(self, '_revid', False):
            # fetch the content (side effect is loading the revid)
            self.content
            self._revision_id = 1
        return self._revision_id
   
   
    @property
    def abstract(self):
        '''
    Plain text summary of the page.
    '''
        try:
            title = self.title['_source']['mine']['dc_abstract']
            self._abstract = title
            return self._abstract
        except KeyError:
            return 'no abstract'
    
    @property
    def format(self):
        '''
    collects the datatype information
    '''
        title = self.title['_source']['mine']['dc_format']
        self._format = title
        return self._format
        
    @property
    def date(self):
        '''
    Dates, on which the papers got published
    '''
        title = self.title['_source']['mine']['dc_date']
        self._date = title
        return self._date
        
    
    @property
    def resource(self):
        '''
    djdjeijdiejdiej
    '''
        title = self.title['_index']
        self._resource = title
        return self._resource

    
    @property
    def titlett(self):
        '''
    Titles of the Papers found
    '''
    
        title_tmp = self.title['_source']['mine']['dc_title']
        self._title = title_tmp
        return self._title
        
   
    @property
    def authors(self):
        '''
    lists each author worked on the same paper
    '''
        try:
            title = self.title['_source']['mine']['schema_org_Person']
            self._authors = title
            return self._authors
        except KeyError:
            return 'no authors'

    
    @property
    def categories(self):
        '''
    List of categories of a page.
    '''

        if not getattr(self, '_categories', False):
            self._categories = [re.sub(r'^Category:', '', x) for x in
                                [link['title']
                                 for link in self.__continued_query({
                                    'prop': 'categories',
                                    'cllimit': 'max'
                                })
                                 ]]

        return self._categories

    @property
    def sections(self):
        '''
    List of section titles from the table of contents on the page.
    '''

        if not getattr(self, '_sections', False):
            query_params = {
                'action': 'parse',
                'prop': 'sections',
            }
            query_params.update(self.__title_query_param)

            request = _wiki_request(query_params)
            self._sections = [section['line'] for section in request['parse']['sections']]

        return self._sections

    def section(self, section_title):
        '''
    Get the plain text content of a section from `self.sections`.
    Returns None if `section_title` isn't found, otherwise returns a whitespace stripped string.

    This is a convenience method that wraps self.content.

    .. warning:: Calling `section` on a section that has subheadings will NOT return
           the full text of all of the subsections. It only gets the text between
           `section_title` and the next subheading, which is often empty.
    '''

        section = u"== {} ==".format(section_title)
        try:
            index = self.content.index(section) + len(section)
        except ValueError:
            return None

        try:
            next_index = self.content.index("==", index)
        except ValueError:
            next_index = len(self.content)

        return self.content[index:next_index].lstrip("=").strip()



def languages():
    '''
  List all the currently supported language prefixes (usually ISO language code).

  Can be inputted to `set_lang` to change the Mediawiki that `wikipedia` requests
  results from.

  Returns: dict of <prefix>: <local_lang_name> pairs. To get just a list of prefixes,
  use `wikipedia.languages().keys()`.
  '''
    response = _wiki_request({
        'meta': 'siteinfo',
        'siprop': 'languages'
    })

    languages = response['query']['languages']

    return {
        lang['code']: lang['*']
        for lang in languages
    }

def _wiki_request(params):
    '''
  Make a request to the Mine API using the given search parameters.
  Returns a parsed dict of the JSON response.
  '''
    global RATE_LIMIT_LAST_CALL
    
    params['format'] = 'json'
    if not 'action' in params:
        params['action'] = 'query'
        
    headers = {
        'Content-type': 'application/json'
    }

    if RATE_LIMIT and RATE_LIMIT_LAST_CALL and \
            RATE_LIMIT_LAST_CALL + RATE_LIMIT_MIN_WAIT > datetime.now():
        # it hasn't been long enough since the last API call
        # so wait until we're in the clear to make the request

        wait_time = (RATE_LIMIT_LAST_CALL + RATE_LIMIT_MIN_WAIT) - datetime.now()
        time.sleep(int(wait_time.total_seconds()))

    r = requests.get(API_URL, params=params, headers=headers)

    if RATE_LIMIT:
        RATE_LIMIT_LAST_CALL = datetime.now()
    
    return r.json()['hits']['hits']

class MineAPI:
    
    """ Wraps Mine API.

    Examples:
        >>> api = MineAPI()
        >>> corpus = api.search('en', ['Barack Obama', 'Hillary Clinton'])
    """
    metas = [
        (data.StringVariable('Title'), lambda doc: getattr(doc, 'titlett')),
        (data.StringVariable('Abstract'), lambda doc: getattr(doc, 'abstract')),
        #(data.StringVariable('Url'), lambda doc: getattr(doc, 'url')),
        (data.StringVariable('Authors'), lambda doc: getattr(doc, 'authors')),
        (data.StringVariable('Date'), lambda doc: getattr(doc, 'date')),
        (data.StringVariable('Format'), lambda doc: getattr(doc, 'format')),
        #(data.ContinuousVariable('Page ID', number_of_decimals=0), lambda doc: int(getattr(doc, 'pageid'))),
        #(data.ContinuousVariable('Revision ID', number_of_decimals=0), lambda doc: int(getattr(doc, 'revision_id'))),
        (data.StringVariable('Resource'), lambda doc: getattr(doc, 'resource')),
        (data.DiscreteVariable('Query'), lambda doc: getattr(doc, 'query')),
    ]
   

    attributes = []
    class_vars = []
    text_features = [m for m, _ in metas]
    string_attributes = [m for m, _ in metas if isinstance(m, data.StringVariable)]

    def __init__(self, on_error=None):
        super().__init__()
        self.on_error = on_error or (lambda x: x)

    def search(self, lang, queries, articles_per_query=10, should_break=None, on_progress=None):
        """ Searches for articles.

        Args:
            lang(str): A language code in ISO 639-1 format.
            queries(list of str): A list of queries.
            should_break (callback): Callback for breaking the computation before the end.
                If it evaluates to True, downloading is stopped and document downloaded till now
                are returned in a Corpus.
            on_progress (callable): Callback for progress bar.
        """
       
        set_lang(lang)

        results = []
        for i, query in enumerate(queries):
            try:
                articles_tmp = search(query, results=articles_per_query)
                articles = articles_tmp
               
                for j, article in enumerate(articles):
                    if callable(should_break) and should_break():
                        break
                    
                    results.extend(self._get(article, query, should_break))

                    if callable(on_progress):
                        on_progress((i*articles_per_query + j+1) / (len(queries) * articles_per_query),
                                    len(results))
            except:
                return []
        
        
        return Corpus.from_documents(results, 'mine', self.attributes,
                                            self.class_vars, self.metas, title_indices=[-1])
        
        
    def _get(self, article, query, should_break, recursive=True):
        try:
            article = page(article)
        
            article.query = query
            
            return [article]
        except DisambiguationError:
            res = []
            if recursive:
                for article in search(article, 20):
                    if callable(should_break) and should_break():
                        break
                    res.extend(self._get(article, query, should_break, recursive=False))
                        
            return res
    
        except PageError:
            return []

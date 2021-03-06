import Bio.Entrez
import Bio.Medline
import logging
import typing
from app.placemats.util import *
from collections import defaultdict, namedtuple

logger = logging.getLogger(__name__)

API_KEY = None

MAX_PER_PAGE = 2000
AUTHOR_NAME = 'AU'
PMID = 'PMID'
ABSTRACT = 'AB'
TITLE = 'TI'
AFFILIATION = 'AD'


def configure_client(email='dev.robot@gmail.com', api_key=None):
    """
    Must be called once before calling any of the other API's
    :param email:
    :param api_key:
    """
    Bio.Entrez.email = email
    global API_KEY
    API_KEY = api_key


def call(procedure, *args, **kwargs):
    """
    Wraps all our calls to Entrez API's. Acts as our 'http interceptor'.
    :type procedure: function
    :param procedure: Entrez function to invoke
    :param args:
    :param kwargs:
    :return:
    """
    logger.debug('Calling {} with args: {}, kwargs: {}'.format(procedure.__name__, args, kwargs))
    if API_KEY:
        kwargs['api_key'] = API_KEY
    handle = procedure(*args, **kwargs)
    if kwargs.get('rettype') == 'medline':
        out = Bio.Medline.parse(handle)
        out = list(out)
    else:
        out = Bio.Entrez.read(handle)
    handle.close()
    return out


def efetch(*args, **kwargs):
    """

    :param args:
    :param kwargs:
    """
    return call(Bio.Entrez.efetch, *args, **kwargs)


def egquery(*args, **kwargs):
    """

    :param args:
    :param kwargs:
    """
    return call(Bio.Entrez.egquery, *args, **kwargs)


def esearch(*args, **kwargs):
    """

    :param args:
    :param kwargs:
    :return:
    """
    return call(Bio.Entrez.esearch, *args, **kwargs)


def pubmed_search(term, skip=0, limit=MAX_PER_PAGE, sort='relevance'):
    retmax = min(limit, MAX_PER_PAGE)
    out = esearch(db='pubmed', sort=sort, term=term, retstart=skip, retmax=retmax)
    logger.info('Pubmed search query: %s ; translation-set: %s', term, out['TranslationSet'])
    return out


def get_medline_infos(ids):
    """
    See https://www.nlm.nih.gov/bsd/mms/medlineelements.html for a description of the medline fields.
    :param ids:
    :return:
    """
    infos = []
    for ids_chunk in chunks(ids, MAX_PER_PAGE):
        infos.extend(efetch(db='pubmed', id=ids_chunk, rettype='medline', retmode='text'))
    return infos


def get_pmids_for_term(term, limit):
    pmids = []
    current = pubmed_search(term)
    current_id_list = current['IdList']
    while len(pmids) < limit and current_id_list:
        pmids.extend(current_id_list)
        current = pubmed_search(term, skip=len(pmids))
        current_id_list = current['IdList']
    return pmids[:limit]


AuthorInfo = namedtuple('AuthorInfo', ['pmid_to_authors', 'author_to_pmids', 'pmid_to_articles'])
Article = namedtuple('Article', ['title', 'abstract'])


def affiliations(term, limit=20_000) -> typing.Dict[str, str]:
    medline_infos = get_medline_infos(get_pmids_for_term(term, limit))
    out = {}
    for m_info in medline_infos:
        if AFFILIATION not in m_info:
            logger.warning('[affiliations] Affiliation not found for term: %s ; PMID: %s', term, m_info[PMID])
            continue
        out[m_info[PMID]] = m_info[AFFILIATION]
    return out


def author_info(term, limit=20_000):
    pmids = get_pmids_for_term(term, limit)
    pmid_to_authors = defaultdict(set)
    author_to_pmids = defaultdict(set)
    pmid_to_articles = {}
    medline_infos = get_medline_infos(pmids)
    for m_info in medline_infos:
        if AUTHOR_NAME not in m_info:
            logger.warning('[author_info] Author name not found for term: %s ; PMID: %s', term, m_info[PMID])
            continue
        pmid = m_info[PMID]
        for name in m_info[AUTHOR_NAME]:
            author_to_pmids[name].add(pmid)
            pmid_to_authors[pmid].add(name)
            pmid_to_articles[pmid] = Article(m_info.get(TITLE), m_info.get(ABSTRACT))
    return AuthorInfo(pmid_to_authors, author_to_pmids, pmid_to_articles)

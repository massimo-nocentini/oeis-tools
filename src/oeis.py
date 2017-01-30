
import threading, re, json, time, textwrap, functools

from itertools import count
from collections import defaultdict
from multiprocessing.dummy import Pool as ThreadPool
from requests import get

Axxxxxx_regex = re.compile('(?P<id>A\d{6,6})')

# FETCHER and UTILS {{{

def fetch_payload(  payload, 
                    then=None,
                    network_error_handler=lambda exc: None,
                    json_decoding_error_handler=lambda GET_result, exc: None,
                    progress_indicator='●'):

    try: 
        GET_result = get("https://oeis.org/search", params=payload,)
    except Exception as e: 
        return network_error_handler(e)

    try:
        doc = GET_result.json()

        if 'results' not in doc or not doc['results']: 
            doc['results'] = []

        print(progress_indicator if progress_indicator else '', end='')

    except Exception as e:
        return json_decoding_error_handler(e, GET_result)

    return then(doc, GET_result) if callable(then) else doc


def promote_id_anchors(text):
    """
    Return a new string where each occurrence of a sequence ref `Axxxxxx` replaced as `<a>` tag.
    """
    return Axxxxxx_regex.sub(r'<a href="http://oeis.org/\g<id>">\g<id></a>', text)

        
def merge_splitted_text(lst):
    """
    Returns a new list where each splitted text in `lst` is joined into a single line of text.
    """

    merged = []

    i = 0
    while i < len(lst):

        if '(Start)' in lst[i] or '(start)' in lst[i]:
            j = i+1
            while j < len(lst) and not ('(End)' in lst[j] or '(end)' in lst[j]): j += 1
            joiner = "\n       - "
            #joiner = "\n<br>"
            merged.append(joiner.join(lst[i:j if j >= len(lst) or lst[j] == '(End)' else j+1])
                          .replace('(Start)', '').replace('(start)', '')
                          .replace('(End)', '').replace('(end)', ''))
            i = j+1
        else:
            merged.append(lst[i])
            i += 1

    return merged

# }}}
    
# LIST and TABLE data representations {{{

class AbstractData:

    def __init__(self, upper_limit):
        self.upper_limit = upper_limit

class ListData(AbstractData):

    def __call__(self, caller, doc):

        seq = doc['data'].split(',')[:self.upper_limit]
        array_template = r'''
$$
\begin{env}{{c|{nel} }}
    n & {nat} \\
    \hline
    {id}(n) & {seq}
\end{env}
$$
        '''
        start = int(doc['offset'].split(',')[0])
        nats_header = [str(i) for i in range(start, len(seq))]
        kwds = {
            'env':'{array}', 
            'nel':'c'*len(seq), 
            'nat':' & '.join(nats_header), 
            'id':'A{:06d}'.format(doc['number']), 
            'seq':' & '.join(seq),
        }
        return array_template.format(**kwds)
        

class TableData(AbstractData):

    def __call__(self, caller, doc):

        n, k = self.upper_limit
        seq = doc['data'].split(',')

        def row(i):
            return  [seq[index] if j <= i else '' 
                        for j in range(k) 
                        for index in [i*(i+1)//2 + j] 
                        if index < len(seq)]

        rows = [' & '.join([str(i)] + row(i)) for i in range(n)]

        array_template = r'''
$$
\begin{env}{{c|{nel} }}
n, k & {nat} \\
\hline
{rows}
\end{env}
$$
        '''
        nats_header = [str(i) for i in range(int(doc['offset'].split(',')[0]), k)]
        kwds = {
            'env': '{array}', 
            'nel': 'c' * (k+1), 
            'nat': ' & '.join(nats_header), 
            'rows': r'\\'.join(rows)
        }
        return array_template.format(**kwds)

# }}}

# BUILDERS {{{

class head_builder:

    def __call__(self, doc):
        head = r"<div align='center'><b><a href='http://oeis.org/A{:06d}'>A{:06d}</a></b>: {}<br></div>".format(
                doc['number'], doc['number'], doc['name'], ) + "\n\nby {}".format(doc['author'])
        return head
        

class keyword_builder:
    
    def __call__(self, doc):
        keyword = "\n_Keywords_: `{}`".format(doc['keyword'])
        return keyword


class data_builder:
    
    def __init__(self, representation):
        self.representation = representation
    
    def __call__(self, doc):

        data = "\n_Data_:\n{}".format(self.representation(self, doc))
        return data

    
class content_builder:
    
    def __init__(self, filter_pred):
        self.filter_pred = filter_pred
    
    def __call__(self, content):
        mapped = map(lambda pair: pair[1],
                     filter(lambda pair: self.filter_pred(pair[0], pair[1].lower()), 
                            zip(count(), map(promote_id_anchors, merge_splitted_text(content)))))
        return list(mapped)
    

class comment_builder(content_builder):
    
    def __call__(self, doc):
        
        if 'comment' not in doc: return ""
        
        comments = super(comment_builder, self).__call__(doc['comment'])
        return ("\n_Comments_:\n   - " + "\n   - ".join(comments)) if comments else ""

class formula_builder(content_builder):
    
    def __call__(self, doc):
        
        if 'formula' not in doc: return ""
        
        formulae = super(formula_builder, self).__call__(doc['formula'])
        return ("\n_Formulae_:\n   - " + "\n   - ".join(formulae)) if formulae else ""
    
class xref_builder(content_builder):
    
    def __call__(self, doc):
        
        if 'xref' not in doc: return ""
        
        xrefs = super(xref_builder, self).__call__(doc['xref'])
        return ("\n_Cross references_:\n   - " + "\n   - ".join(xrefs)) if xrefs else ""

class link_builder(content_builder):
    
    def __call__(self, doc):
        
        if 'link' not in doc: return ""
        
        links = super(link_builder, self).__call__(doc['link'])
        return ("\n_Links_:\n   - " + "\n   - ".join(links)) if links else ""

class reference_builder(content_builder):
    
    def __call__(self, doc):
        
        if 'reference' not in doc: return ""
        
        references = super(reference_builder, self).__call__(doc['reference'])
        return ("\n_References_:\n   - " + "\n   - ".join(references)) if references else ""

# }}}
    
def pretty_print(doc, 
                 data_only=False,
                 head=None,
                 keyword=None, 
                 preamble=True,
                 data_representation=None, 
                 #wrapper=functools.partial(textwrap.wrap, width=80, replace_whitespace=False),   
                 comment=lambda i, c: True,
                 formula=lambda i, c: True,
                 xref=lambda i, c: True,
                 link=lambda i, c: False and "broken link" not in c,
                 reference=lambda i, c: False):
    
    if not data_representation:
        data_representation = TableData(upper_limit=(10,10)) if 'tabl' in doc['keyword'] else ListData(upper_limit=15)

    builders = [head_builder(), 
                keyword_builder(), 
                data_builder(representation=data_representation)] if preamble else []
    
    if not data_only:
        builders.extend([comment_builder(filter_pred=comment), 
                         formula_builder(filter_pred=formula), 
                         xref_builder(filter_pred=xref),
                         link_builder(filter_pred=link), 
                         reference_builder(filter_pred=reference)])
    
    paragraphs = [paragraph 
                    for builder in builders 
                    for paragraph in [builder(doc)]]

    return "\n".join(paragraphs)


def search( A_id=None, seq=None, query="",
            start=0, max_results=None, table=False, xref=[], only_possible_matchings=False, **kwds):

    from IPython.display import Markdown

    query_components = [] # a list of query components, as strings to be joined later

    if isinstance(A_id, (str, )) and Axxxxxx_regex.match(A_id): 
        query_components.append("id:{}".format(A_id))
    elif seq: 
        query_components.append((", " if isinstance(seq, list) else " ").join(map(str,seq)))
    elif query: 
        query_components.append(query) 
    else:
        raise ValueError('No argument for searching.')

    if table: query_components.append("keyword:tabl")
    for r in xref: query_components.append("xref:A{:06d}".format(A_id))
    for k,v in kwds.items(): query_components.append("{}:{}".format(k,v))

    def connection_error(exc):
        return lambda **pp_kwds: Markdown("<hr>__Connection Error__<hr>")

    def json_error(exc, GET_result):
        return lambda **pp_kwds: Markdown("<hr>__JSON decoding Error__:\n```{}```<hr>".format(GET_result.text))

    def make_searchable(doc, GET_result):

        def searchable(**pp_kwds):
            results_description = r"_Results for query: <a href='{url}'>{url}</a>_<br><hr>".format(url=GET_result.url)
            inner_results = [pretty_print(result, **pp_kwds) 
                                for i, result in enumerate(doc['results']) 
                                if not max_results or i < max_results]
            return Markdown(results_description + "\n<hr>".join(inner_results))

        return searchable

    def possible_matchings(doc, GET_result):

        def searchable(term_src):

            matches = [r"<a href='http://oeis.org/A{:06d}'>A{:06d}</a>".format(result['number'], result['number']) 
                       for result in doc['results']]

            return r'<tr><td style="white-space:nowrap;">$${math}$$</td><td>{seqs}</td></tr>'.format(
                math=term_src, seqs=", ".join(matches))

        return searchable

    return fetch_payload(payload={"fmt": "json", "start": start, "q": ' '.join(query_components)},  
                         then=possible_matchings if only_possible_matchings else make_searchable,
                         network_error_handler=connection_error,
                         json_decoding_error_handler=json_error)




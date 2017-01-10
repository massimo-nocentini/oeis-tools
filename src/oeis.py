
import threading, re, json, time
import networkx as nx

from itertools import count
from collections import defaultdict
from multiprocessing.dummy import Pool as ThreadPool
from requests import get


#________________________________________________________________________

def promote_id_anchors(text):
    """
    Return a new string where each occurrence of a sequence ref `Aoooooo` replaced as `<a>` tag.
    """
    
    import re
    return re.compile('(?P<id>A\d{6,6})').sub(r'<a href="http://oeis.org/\g<id>">\g<id></a>', text)

        
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
    
#________________________________________________________________________

class head_builder:

    def __call__(self, doc):
        head = r"<div align='center'><b><a href='http://oeis.org/A{:06d}'>A{:06d}</a></b>: {}<br></div>".format(
                doc['number'], doc['number'], doc['name'], ) + "\n\nby {}".format(doc['author'])
        return head
        
class keyword_builder:
    
    def __call__(self, doc):
        keyword = "\n_Keywords_: `{}`".format(doc['keyword'])
        return keyword
        
class AbstractData:

    def __init__(self, upper_limit):
        self.upper_limit = upper_limit

class ListData(AbstractData):

    def __call__(self, caller, doc):

        seq = doc['data'].split(',')[:self.upper_limit]
        array_template = r'''
$$
\begin{env}{{c|{nel}}}
n & {nat} \\
\hline
{id}(n) & {seq}
\end{env}
$$
'''.format(env="{array}",
           nel='c'*len(seq), 
           nat=" & ".join([str(i) for i in range(int(doc['offset'].split(',')[0]), len(seq))]),
           id="A{:06d}".format(doc['number']), 
           seq = " & ".join(seq))

        return array_template
        

class TableData(AbstractData):

    def __call__(self, caller, doc):

        seq = doc['data'].split(',')
        n, k = self.upper_limit

        rows = r'\\'.join([' & '.join([str(i)] + [seq[index] if j <= i else '' for j in range(k) for index in [i*(i+1)//2 + j] if index < len(seq)]) for i in range(n)])

        array_template = r'''
$$
\begin{env}{{c|{nel}}}
n, k & {nat} \\
\hline
{rows}
\end{env}
$$
'''.format(env="{array}",
           nel='c' * (k+1), 
           nat=" & ".join([str(i) for i in range(int(doc['offset'].split(',')[0]), k)]),
           rows=rows)

        return array_template

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

#________________________________________________________________________
    
def pretty_print(doc, 
                 data_only=False,
                 head=None,
                 keyword=None, 
                 preamble=True,
                 data_representation=None, 
                 comment=lambda i, c: True,
                 formula=lambda i, c: True,
                 xref=lambda i, c: True,
                 link=lambda i, c: "broken link" not in c,
                 reference=lambda i, c: True,):
    
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
    
    descr = "\n".join([builder(doc) for builder in builders])
    return descr


def oeis_search(id=None, seq=None, query="", start=0, table=False, xref=[], only_possible_matchings=False, **kwds):

    # the following imports are too specific to appear at the top of the module.
    from requests import get
    from IPython.display import Markdown

    progress_indicator=kwds.pop('progress_indicator', '*') 

    query_components = [] # a list of query components, as strings to be joined later

    if id: query_components.append("id:A{:06d}".format(id))
    elif seq: query_components.append((", " if isinstance(seq, list) else " ").join(map(str,seq)))
    else: query_components.append(query) 

    if table: query_components.append("keyword:tabl")
    for r in xref: query_components.append("xref:A{:06d}".format(id))
    for k,v in kwds.items(): query_components.append("{}:{}".format(k,v))

    def connection_error(exc):
        return lambda **pp_kwds: Markdown("<hr>__Connection Error__<hr>")

    def json_error(GET_result, exc):
        return lambda **pp_kwds: Markdown("<hr>__JSON decoding Error__:\n```{}```<hr>".format(GET_result.text))

    def make_searchable(doc, GET_result):

        def searchable(**pp_kwds):
            results_description = "_Results for query: <a href='{url}'>{url}</a>_<br><hr>".format(url=GET_result.url)
            inner_results = [pretty_print(result, **pp_kwds) for result in doc['results']]
            return Markdown(results_description + "\n<hr>".join(inner_results))

        return searchable

    def possible_matchings(doc, GET_result):

        def searchable(term_src, no_matchings="no matchings found."):

            matches = [r"<a href='http://oeis.org/A{:06d}'>A{:06d}</a>".format(result['number'], result['number']) 
                       for result in doc['results']]
            
            if not matches: matches = []

            return r'<tr><td style="white-space:nowrap;">$${math}$$</td><td>{seqs}</td></tr>'.format(math=term_src, seqs=", ".join(matches))

        return searchable

    return fetch_payload(payload={"fmt": "json", "start": start, "q": ' '.join(query_components)},  
                         then=possible_matchings if only_possible_matchings else make_searchable,
                         network_error_handler=connection_error,
                         progress_indicator=progress_indicator,
                         json_decoding_error_handler=json_error)


def cross_references(xref):
    regex = re.compile('(?P<id>A\d{6,6})')
    return {int(r[1:]) for references in xref for r in regex.findall(references)}

def fetch_payload(  payload, 
                    then=None,
                    network_error_handler=lambda exc: None, 
                    progress_indicator='*',
                    json_decoding_error_handler=lambda GET_result, exc: None):

    try: 
        GET_result = get("https://oeis.org/search", params=payload,)
    except Exception as e: 
        return network_error_handler(e)

    try:
        doc = GET_result.json()
        if not doc['results']: doc['results'] = []
        print(progress_indicator if progress_indicator else '', end='')
    except Exception as e:
        return json_decoding_error_handler(GET_result, e)

    return then(doc, GET_result) if callable(then) else doc

def adjust_crossreferences(graph):

    for k, v in graph.items():

        xrefs = cross_references(v['xref']) if 'xref' in v else set()
        v['xref_as_set'] = {xr for xr in xrefs if xr in graph} 

        for ref in v['xref_as_set']:

            referenced = graph[ref]
            if 'referees' not in referenced: referenced['referees'] = set()
            referenced['referees'].add(k)

    return graph

def oeis_graph(seq_id, depth=2, workers=20, post_processing=[adjust_crossreferences]):
        
    sink = {}
    unknown = 'unknown'
    
    def fetch(seq_id):

        payload = {"fmt": "json", "q": "id:A{:06d}".format(seq_id)}

        def error_handler(GET_result, exc):
            print("sequence {} needs retry; current GET response text:\n{}\n".format(seq_id, GET_result.text))
            return None

        doc = fetch_payload(payload, json_decoding_error_handler=error_handler)
        return doc['results'].pop() if doc['results'] else unknown


    def not_seen_so_far(ref_seq_id):
        return ref_seq_id not in sink
    
    def recursion(sequences, step):
        
        if step > depth: 
            print("\nHorizon reached.")
            return

        print("\nFringe at distance {}, {} sequences to fetch.".format(step, len(sequences)))

        pool = ThreadPool(workers) # Make the Pool of workers

        # Open the urls in their own threads and return the results
        results = pool.map(lambda seq_id: (seq_id, fetch(seq_id)), sequences)

        #close the pool and wait for the work to finish
        pool.close()
        pool.join()

        cross_sequences = set()
        retry = set() 

        for seq_id, result in results: 
            
            if not result:
                retry.add(seq_id)
                continue

            if result is unknown: continue

            # since `recursion` is called if `seq_id` hasn't been fetched
            sink.update({int(result['number']): result}) 

            # preparing for recursion
            cross_sequences |= cross_references(result['xref']) if 'xref' in result else set()
            
        if retry:
            # sleep for some seconds, then retry
            secs = 3
            print("There are {} sequences to be downloaded again. Sleeping for {} secs than redo.".format(len(retry), secs))
            time.sleep(secs)
            recursion(set(filter(not_seen_so_far, retry)), step)

        recursion(set(filter(not_seen_so_far, cross_sequences)), step+1)
        
    recursion({seq_id}, step=0)
    
    for process in post_processing:
        sink = process(sink)

    return sink
    

def load_graph(filename):

    with open(filename, 'r') as f:

        graph = {int(k):v for k, v in adjust_crossreferences(json.load(f)).items()}
        return adjust_crossreferences(graph)


def fetch_graph(filename, **kwds): 

    def save(graph):
        with open(filename, 'w') as f:
            json.dump(graph, f)

    start_timestamp = time.time()

    graph = oeis_graph(post_processing=[], **kwds)

    end_timestamp = time.time()

    print("Elapsed time: {:3} secs.".format(end_timestamp - start_timestamp))

    save(graph)

    print("Graph saved.")

#________________________________________________________________________

def make_nx_graph(graph, summary=True, digraph=True, 
                  node_remp=lambda n, G: False, 
                  edge_remp=lambda u, v, G: False):

    G = nx.DiGraph() if digraph else nx.Graph()

    for seq_id, v in graph.items():
        for ref_seq_id in v['xref_as_set']:
            G.add_edge(seq_id, ref_seq_id)

    G.remove_nodes_from([n for n in G.nodes() if node_remp(n, G)])
    G.remove_edges_from([(u, v) for u, v in G.edges() if edge_remp(u, v, G)])
            
    if summary:
        print("A graph with {} nodes and {} edges will be drawn".format(len(G.nodes()),len(G.edges())))
        
    return G

def draw_nx_graph(G, nodes_colors={}, filename=None, nodes_labels={}):
    
    import matplotlib.pyplot as plt

    if 'draw' not in nodes_labels: nodes_labels['draw'] = True
    
    nc = defaultdict(lambda: 'gray')
    nc.update(nodes_colors)
    
    pos=nx.spring_layout(G)#, iterations=200) # positions for all nodes

    degrees = G.in_degree() if G.is_directed() else G.degree()
    for seq_id in G.nodes():
        nx.draw_networkx_nodes(G, pos, nodelist=[seq_id], 
                               node_color=nc[seq_id],
                               node_size=degrees[seq_id]*10, 
                               alpha=0.8)

    """
    nx.draw_networkx_nodes(G,pos,
                           nodelist=set(G.nodes())-set(favorite_nodes.keys()),
                           node_color='r',
                           node_size=500,
                       alpha=0.8)
    """
    
    nx.draw_networkx_edges(G,pos,width=1.0,alpha=0.5)
    
    if nodes_labels['draw']:
        ls = {n:nodes_labels[n] if n in nodes_labels else (str(n) if G.in_degree()[n] > 10 else "") 
              for n in G.nodes()}
        nx.draw_networkx_labels(G,pos,ls,font_size=16)

    plt.axis('off')
    if filename: plt.savefig(filename) # save as png
    else: plt.show()



import json, textwrap, functools

from commons import *
    
# LIST and TABLE data representations {{{

class AbstractData:

    def __init__(self, upper_limit):
        self.upper_limit = upper_limit

    def __call__(self, doc, interface):
        return interface.dispatch(on=self, payload={'doc':doc})

class ListData(AbstractData):

    def for_notebook(self, nb, doc):

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
        
    def for_console(self, cli, doc):

        from sympy import Matrix, pretty

        seq = doc['data'].split(',')[:self.upper_limit]

        L = Matrix(1, min(len(seq), self.upper_limit), lambda _, j: int(seq[j]))

        return pretty(L)

class TableData(AbstractData):

    def for_notebook(self, nb, doc):

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

    def for_console(self, cli, doc):

        from sympy import Matrix, pretty, IndexedBase

        n, k = self.upper_limit
        seq = doc['data'].split(',')
        d = IndexedBase('d')

        def coeff(i, j):
            if i < j: return 0
            index = i*(i+1)//2 + j
            return seq[index] if index < len(seq) else d[i, j]

        M = Matrix(n, k, coeff)

        return pretty(M)

# }}}

# BUILDERS {{{

class head_builder:

    def __init__(self, interface, handler):
        self.interface = interface
        self.handler = handler

    def __call__(self, doc):
        return self.interface.dispatch(on=self, payload={'doc': doc})

    def for_notebook(self, nb, doc):
        head = r"<div align='center'><b><a href='http://oeis.org/A{:06d}'>A{:06d}</a></b>: {}<br></div>".format(
                doc['number'], doc['number'], doc['name'], ) + "\n\nby {}".format(doc['author'])
        return head
        
    def for_console(self, cli, doc):
        filled_name = self.handler.head_filler(doc['name'])
        head = '\n{}\n\nby {}'.format(filled_name, doc['author'])
        return head

class keyword_builder:
    
    def __call__(self, doc):
        keyword = "\n_Keywords_: `{}`".format(doc['keyword'])
        return keyword


class data_builder:
    
    def __init__(self, interface, representation):
        self.interface = interface
        self.representation = representation
    
    def __call__(self, doc):
        data = "\n_Data_:\n{}".format(self.representation(doc, self.interface))
        return data

    
class content_builder:
    
    def __init__(self, filter_pred, handler):
        self.filter_pred = filter_pred
        self.handler = handler
    
    def process(self, content):
        
        processed = self.merge_splitted_text(content)
        post = getattr(self.handler, 'post', lambda i: i)
        return [post(c) for i, c in enumerate(processed) if self.filter_pred(i, c)]

    def merge_splitted_text(self, lst):
        """
        Returns a new list where each splitted text in `lst` is joined into a single line of text.
        """

        lines = []

        def delete_start_end_placeholders(line):
            l = line.replace('(Start)', '').replace('(start)', '')
            return l.replace('(End)', '').replace('(end)', '')

        i = 0
        while i < len(lst):

            line = lst[i]
            
            if '(start)' in line.lower():

                clean_firstline = delete_start_end_placeholders(line)
                if clean_firstline:
                    # the very first line of a chuck should 
                    # be indent according to the outer filler
                    lines.append(self.handler.out_filler(clean_firstline))

                subchunk = []

                for j in range(i+1, len(lst)):
                    subline = lst[j]
                    subchunk.append(subline)
                    if '(end)' in subline.lower():

                        clean_lastline = delete_start_end_placeholders(subline)
                        if not clean_lastline:
                            del subchunk[-1]
                        else:
                            subchunk[-1] = clean_lastline

                        break
                  
                
                atomic_chunk = '\n'.join(map(self.handler.in_filler, subchunk))
                lines.append(atomic_chunk)

                i = j+1
            else:
                lines.append(self.handler.out_filler(line))
                i += 1

        return lines

class comment_builder(content_builder):
    
    def __call__(self, doc):
        
        if 'comment' not in doc: return ""
        
        comments = self.process(doc['comment'])
        return ("\n_Comments_:\n" + "\n".join(comments)) if comments else ""

class formula_builder(content_builder):
    
    def __call__(self, doc):
        
        if 'formula' not in doc: return ""
        
        formulae = self.process(doc['formula'])
        return ("\n_Formulae_:\n" + "\n".join(formulae)) if formulae else ""
    
class xref_builder(content_builder):
    
    def __call__(self, doc):
        
        if 'xref' not in doc: return ""
        
        xrefs = self.process(doc['xref'])
        return ("\n_Cross references_:\n" + "\n".join(xrefs)) if xrefs else ""

class link_builder(content_builder):
    
    def __call__(self, doc):
        
        if 'link' not in doc: return ""
        
        links = self.process(doc['link'])

        return ("\n_Links_:\n" + "\n".join(links)) if links else ""

class reference_builder(content_builder):
    
    def __call__(self, doc):
        
        if 'reference' not in doc: return ""
        
        references = self.process(doc['reference'])
        return ("\n_References_:\n" + "\n".join(references)) if references else ""

# }}}
    
default_comment_predicate=lambda i, c: True
default_formula_predicate=lambda i, c: True
default_xref_predicate=lambda i, c: True
default_link_predicate=lambda i, c: False and "broken link" not in c
default_reference_predicate=lambda i, c: False
default_upper_limits = {'list':15, 'table':(10,10)}

def pretty_print(doc, 
                 interface,
                 data_only=False,
                 head=None,
                 keyword=None, 
                 preamble=True,
                 data_representation=default_upper_limits, 
                 comment=default_comment_predicate,
                 formula=default_formula_predicate,
                 xref=default_xref_predicate,
                 link=default_link_predicate,
                 reference=default_reference_predicate):
    
    if not isinstance(data_representation, AbstractData):
        if 'tabl' in doc['keyword']:
            data_representation = TableData(upper_limit=data_representation['table'])
        else: 
            data_representation = ListData(upper_limit=data_representation['list'])

    handler = interface.dispatch(on=text_handler())

    builders = [head_builder(interface, handler), 
                keyword_builder(), 
                data_builder(interface, data_representation)] if preamble else []
    
    if not data_only:
        builders.extend([comment_builder(filter_pred=comment, handler=handler), 
                         formula_builder(filter_pred=formula, handler=handler), 
                         xref_builder(filter_pred=xref, handler=handler),
                         link_builder(filter_pred=link, handler=handler), 
                         reference_builder(filter_pred=reference, handler=handler)])
    
    paragraphs = [paragraph 
                    for builder in builders 
                    for paragraph in [builder(doc)]
                    if paragraph]

    return "\n".join(paragraphs + ['']) # the last '' to make a final empty line


def search( A_id=None, seq=None, query=None, 
            cache_info={'cache_dir': './fetched/', 'most_recents': None, 'cache_first': True},
            interface=notebook(),
            start=0, max_results=None, table=False, xref=[], 
            only_possible_matchings=False, **kwds):

    query_components = [] # a list of query components, as strings to be joined later

    if isinstance(A_id, (str, )) and Axxxxxx_regex.match(A_id): 
        query_components.append("id:{}".format(A_id))
        cache_info['id'] = A_id
    elif seq: 
        ready = (", " if isinstance(seq, list) else " ").join(map(str,seq))
        query_components.append(ready)
        cache_info['seq'] = seq
    elif query: 
        query_components.append(query) 

    if table: query_components.append("keyword:tabl")
    for r in xref: query_components.append("xref:A{:06d}".format(A_id))
    for k,v in kwds.items(): query_components.append("{}:{}".format(k,v))

    def connection_error(exc):
        return lambda **pp_kwds: Markdown("<hr>__Connection Error__<hr>")

    def json_error(exc, GET_result):
        return lambda **pp_kwds: Markdown("<hr>__JSON decoding Error__:\n```{}```<hr>".format(GET_result.text))

    def make_searchable(doc, GET_result):

        def searchable(**pp_kwds):

            results = [pretty_print(result, interface, **pp_kwds) 
                                for i, result in enumerate(doc['results']) 
                                if not max_results or i < max_results]

            return interface.dispatch(on=oeis_results_composer(results, doc, GET_result))

        return searchable

    def possible_matchings(doc, GET_result):

        def searchable(term_src):

            matches = [r"<a href='http://oeis.org/A{:06d}'>A{:06d}</a>".format(result['number'], result['number']) 
                       for result in doc['results']]

            return r'<tr><td style="white-space:nowrap;">$${math}$$</td><td>{seqs}</td></tr>'.format(
                math=term_src, seqs=", ".join(matches))

        return searchable

    return fetch_oeis_payload(
                dolocal=cache_info,
                payload={"fmt": "json", "start": start, "q": ' '.join(query_components)},  
                then=possible_matchings if only_possible_matchings else make_searchable, 
                network_error_handler=connection_error, 
                json_decoding_error_handler=json_error,
                progress_indicator=None)

# DISPATCHING {{{

class oeis_results_composer:

    def __init__(self, results, doc, GET_result):
        self.results = results
        self.doc = doc
        self.GET_result = GET_result

    def for_notebook(self, nb):
        from IPython.display import Markdown
        results_description = r"_Results for query: <a href='{url}'>{url}</a>_<br><hr>".format(
            url=self.GET_result.url)
        return Markdown(results_description + "\n<hr>".join(self.results))

    def for_console(self, cli):
        dashes = '_' * cli.width
        finished = '\n{}\n'.format(dashes).join(self.results)
        if cli.print_results:
            print(finished)
        else: 
            return finished

class text_handler:

    def for_notebook(self, nb):
        
        width = 80
        self.head_filler = self.make_filler(depth=0, marker='', width=width)
        self.out_filler = self.make_filler(depth=0, marker='-', width=width)
        self.in_filler = self.make_filler(depth=1, marker='-', width=width)
        self.post = seqid_to_ahref # for post processing
        return self

    def for_console(self, cli):

        self.head_filler = self.make_filler(depth=0, marker='', width=cli.width)
        self.out_filler = self.make_filler(depth=1, marker='●', width=cli.width)
        self.in_filler = self.make_filler(depth=2, marker='○', width=cli.width)
        return self

    def make_filler(self, depth, marker, width):
        tabs = ' ' * (4*depth)
        return functools.partial(   textwrap.fill, 
                                    width=width, 
                                    replace_whitespace=False,
                                    break_long_words=False,
                                    break_on_hyphens=False, 
                                    tabsize=4,
                                    initial_indent=tabs + marker + ' ',
                                    subsequent_indent=tabs + '  ')

# }}}

# argument parsing {{{

def handle_cli_arguments():

    import argparse

    def list_or_set(seq_as_str):
        seq = eval(seq_as_str)
        if isinstance(seq, (list, set)):
            return seq
        else:
            raise ValueError

    class upper_limit_eval_action(argparse.Action):
    
        def __call__(self, parser, namespace, values, option_string, **kwds): 
            ''' https://docs.python.org/3/library/argparse.html#action-classes '''
            user_dict = eval(values)
            if isinstance(user_dict, dict):
                namespace.upper_limit.update(user_dict)

    def make_eval_lambda_action(fieldname):

        class eval_lambda_action(argparse.Action):

            def __call__(self, parser, namespace, values, option_string): 
                lambda_expr = eval(values)
                if callable(lambda_expr):
                    setattr(namespace, fieldname, lambda_expr)

        return eval_lambda_action # actually the class, not an instance


    parser = argparse.ArgumentParser(description='OEIS Pretty Printer.')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--id', help='Sequence id, given in the form Axxxxxx', type=OEIS_sequenceid)
    group.add_argument('--seq', help='Literal sequence, ordered \'[...]\' or presence \'{...}\' ', type=list_or_set)
    group.add_argument('--query', help='Open query for plain search, in the form \'...\'')
    group.add_argument('--most-recents', help="Print the most recent sequences ranking by M in ACCESS or MODIFY, looking into --cache-dir, at most --max-results (defaults to None)", 
                        default=None, metavar='M', choices={'ACCESS', 'MODIFY'})

    parser.add_argument("--force-fetch", help="Bypass cache fetching again, according to --cache-dir (defaults to False)", 
                        action="store_true", default=False)
    parser.add_argument("--cache-dir", help="Cache directory (defaults to ./fetched/)",
                        default='./fetched/')

    parser.add_argument("--tables-only", help="Print matrix sequences only (defaults to False)", 
                        action="store_true", default=False)
    parser.add_argument("--start-index", metavar='S', help="Start from result at rank position S (defaults to 0)",
                        type=int, default=0)
    parser.add_argument("--max-results", metavar='R', help="Pretty print the former R <= 10 results (defaults to 10)",
                        type=int, default=10)#, choices=range(1, 11))

    parser.add_argument("--data-only", help="Show only data repr and preamble (defaults to False)", 
                        action="store_true", default=False)
    parser.add_argument('--upper-limit', metavar='U',
                        help='Upper limit for data repr: U is a dict \'{"list":i, "table":(r, c)}\' where i, r and c are ints (defaults to i=15, r=10 and c=10), respectively)', 
                        action=upper_limit_eval_action, default=default_upper_limits)

    parser.add_argument('--comment-filter', metavar='C', 
                        help='Apply filter C to comments, where C is Python `lambda` predicate \'lambda i,c: ...\' referring to i-th comment c',
                        default=default_comment_predicate, action=make_eval_lambda_action(fieldname='comment_filter'))
    parser.add_argument('--formula-filter', metavar='F', 
                        help='Apply filter F to formulae, where F is Python `lambda` predicate \'lambda i,f: ...\' referring to i-th formula f',
                        default=default_formula_predicate, action=make_eval_lambda_action(fieldname='formula_filter'))
    parser.add_argument('--xrefs-filter', metavar='X', 
                        help='Apply filter X to cross refs, where X is Python `lambda` predicate \'lambda i,x: ...\' referring to i-th xref x',
                        default=default_xref_predicate, action=make_eval_lambda_action(fieldname='xrefs_filter'))
    parser.add_argument('--link-filter', metavar='L', 
                        help='Apply filter L to links, where L is Python `lambda` predicate \'lambda i,l: ...\' referring to i-th link l',
                        default=default_link_predicate, action=make_eval_lambda_action(fieldname='link_filter'))
    parser.add_argument('--cite-filter', metavar='R', 
                        help='Apply filter R to citation, where R is Python `lambda` predicate \'lambda i,r: ...\' referring to i-th citation r',
                        default=default_reference_predicate, action=make_eval_lambda_action(fieldname='cite_filter'))

    parser.add_argument("--console-width", metavar='W', help="Console columns (defaults to 72)",
                        type=int, default=72)

    args = parser.parse_args()
    return args

# }}}

# main {{{

if __name__ == "__main__":

    args = handle_cli_arguments()

    searchable = search(A_id=args.id, seq=args.seq, query=args.query,
                        cache_info={'cache_dir': args.cache_dir, 
                                    'most_recents': args.most_recents, 
                                    'cache_first': not args.force_fetch},
                        interface=console(print_results=False, width=args.console_width),
                        start=args.start_index,
                        max_results=args.max_results,
                        table=args.tables_only)

    searchable = functools.partial( searchable, # which is really the `pretty_print` function
                                    data_representation=args.upper_limit,
                                    data_only=args.data_only,
                                    comment=args.comment_filter,
                                    formula=args.formula_filter,
                                    xref=args.xrefs_filter,
                                    link=args.link_filter,
                                    reference=args.cite_filter)
    
    results = searchable()

    print(results)

# }}}    

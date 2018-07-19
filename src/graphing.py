
import networkx as nx
import commons

from collections import defaultdict

def graph_load(cache_dir='./fetched/'):
    docs = commons.cache_reify(cache_dir)
    graph = adjust_crossreferences(docs)
    return graph

def adjust_crossreferences(docs):
    
    graph = {k:v['results'].pop() for k, v in docs.items()}

    for k, result in graph.items():

        xrefs = commons.cross_references(result['xref']) if 'xref' in result else set()
        
        # finally, ensure `closed-world` property:
        result['xref_as_set'] = {xr for xr in xrefs if xr in graph}  

        for ref in result['xref_as_set']:
            referenced = graph[ref]
            if 'referees' not in referenced: 
                referenced['referees'] = set()
            referenced['referees'].add(k)

    return graph

def make_nx_graph(graph, digraph=False, 
                  node_remp=lambda n, G: False, 
                  edge_remp=lambda u, v, G: False):

    G = nx.DiGraph() if digraph else nx.Graph()

    for seq_id, v in graph.items():
        for ref_seq_id in v['xref_as_set']:
            G.add_edge(seq_id, ref_seq_id)

    G.remove_nodes_from([n for n in G.nodes() if node_remp(n, G)])
    G.remove_edges_from([(u, v) for u, v in G.edges() if edge_remp(u, v, G)])
        
    return G

def draw_nx_graph(  G, nodes_colors={}, 
                    filename=None, nodes_labels={}, dpi=600,
                    layout=lambda l: l.shell_layout):
    
    import matplotlib.pyplot as plt

    if 'draw' not in nodes_labels: nodes_labels['draw'] = True
    
    nc = defaultdict(lambda: 'gray')
    nc.update(nodes_colors)
     
    l = layout(nx.layout)
    pos = l(G)

    degrees = G.in_degree() if G.is_directed() else G.degree()
    for seq_id in G.nodes():
        nx.draw_networkx_nodes(G, pos, nodelist=[seq_id], 
                               node_color=nc[seq_id],
                               node_size=degrees[seq_id]*10, 
                               alpha=0.8)
    
    nx.draw_networkx_edges(G,pos,width=1.0,alpha=0.5)
    
    if nodes_labels['draw']:
        ls = {n:nodes_labels[n] if n in nodes_labels else '' 
              for n in G.nodes()}
        nx.draw_networkx_labels(G,pos,ls,font_size=16)

    plt.axis('off')
    if filename: plt.savefig(filename, dpi=dpi)
    else: plt.show()


# argument parsing {{{ 

def handle_cli_arguments(): 
    
    import argparse 
    
    def layout_type(l):
        '''
        https://networkx.github.io/documentation/development/_modules/networkx/drawing/layout.html
        '''

        layout_selector = None

        if l == 'RANDOM':
            layout_selector = lambda l: l.random_layout
        if l == 'CIRCULAR':
            layout_selector = lambda l: l.circular_layout
        elif l == 'SHELL':
            layout_selector = lambda l: l.shell_layout
        elif l == 'FRUCHTERMAN-REINGOLD' or l == 'SPRING':
            layout_selector = lambda l: l.fruchterman_reingold_layout
        elif l == 'SPECTRAL':
            layout_selector = lambda l: l.spectral_layout
        else:
            raise ValueError

        return layout_selector
            

    parser = argparse.ArgumentParser(description='OEIS grapher.')

    parser.add_argument('filename', metavar='F', help='Save image in file F.')
    parser.add_argument("--directed", help="Draw directed edges", action="store_true")
    parser.add_argument("--cache-dir", help="Cache directory (defaults to ./fetched/)",
                        default='./fetched/')
    parser.add_argument("--graphs-dir", help="Graphs directory (defaults to ./graphs/)",
                        default='./graphs/')
    parser.add_argument("--dpi", help="Resolution in DPI (defaults to 600)",
                        default=600, type=int)
    parser.add_argument("--layout", help="Graph layout, choose from: {RANDOM, CIRCULAR, SHELL, FRUCHTERMAN-REINGOLD, SPRING, SPECTRAL} (defaults to SHELL)",
                        default='SHELL', type=layout_type,) 

    args = parser.parse_args()
    return args

# }}}

# main {{{

if __name__ == "__main__":

    args = handle_cli_arguments()

    docs = commons.cache_reify(args.cache_dir)

    graph = adjust_crossreferences(docs)

    nxgraph = make_nx_graph(graph, digraph=args.directed, )

    draw_nx_graph(nxgraph, filename=args.graphs_dir + args.filename, layout=args.layout)

# }}}    

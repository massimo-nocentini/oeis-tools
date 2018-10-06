
import networkx as nx
import commons
import math
import random

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

    G, edge_symbol = (nx.DiGraph(), '->') if digraph else (nx.Graph(), '--')

    edge_symbol = '--'
    edges = []
    reds, greens, blues = {}, {}, {}
    for seq_id, v in graph.items():
        for ref_seq_id in v['xref_as_set']:
            G.add_edge(seq_id, ref_seq_id)
            edges.append("{} {} {}".format(seq_id, edge_symbol, ref_seq_id))

        red, green, blue = map(len, [v.get('comment',[]),
                                     v.get('reference', []),
                                     v.get('xref_as_set', [])])
        reds[seq_id] = red
        greens[seq_id] = green
        blues[seq_id] = blue

    max_red = max(reds.values())
    reds = {k:(255*v/(max_red if max_red else 1)) for k,v in reds.items()}

    max_green = max(greens.values())
    greens = {k:(255*v/(max_green if max_green else 1)) for k,v in greens.items()}

    max_blue = max(blues.values())
    blues = {k:(255*v/(max_blue if max_blue else 1)) for k,v in blues.items()}

    nodes = {k:(reds[k], greens[k], blues[k]) for k in reds.keys()}

    G.remove_nodes_from([n for n in G.nodes() if node_remp(n, G)])
    G.remove_edges_from([(u, v) for u, v in G.edges() if edge_remp(u, v, G)])

    return G, nodes, edges

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

    nxgraph, nodes, edges = make_nx_graph(graph, digraph=args.directed, )

    labels = []
    for node, color in nodes.items():
        r, g, b = color 
        c = math.floor((.3*r + .59*g + .11*b) / 1)
        labels.append("{} {{ color:#{:02X}{:02X}{:02X} }}".format(
            node, math.floor(255-r), math.floor(255-g), math.floor(255-b)))
            #node, math.floor(255-c), math.floor(255-c), math.floor(255-c)))

    if False:
        cc = nx.strongly_connected_components(nxgraph)
        #cc = nx.dominating_set(nxgraph, start_with='A000045')
        #cc = nx.find_cliques(nxgraph)

        nodes = []
        for c in cc:
            color = format(math.floor(random.random()*16777215), '02x')
            for node in c:
                nodes.append("{} {{ color:#{} }}".format(node, color))

    with open(args.graphs_dir + args.filename, "w") as f:
        f.write("-> { color: #ffffff }\n")
        f.write("\n".join(edges + labels))

    #draw_nx_graph(nxgraph, filename=args.graphs_dir + args.filename, layout=args.layout)

# }}}

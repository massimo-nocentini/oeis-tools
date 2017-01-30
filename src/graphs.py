
import networkx as nx

def cross_references(xref):
    return {int(r[1:])  for references in xref 
                        for r in Axxxxxx_regex.findall(references)}

def adjust_crossreferences(graph):

    for k, v in graph.items():

        xrefs = cross_references(v['xref']) if 'xref' in v else set()
        v['xref_as_set'] = {xr for xr in xrefs if xr in graph} 

        for ref in v['xref_as_set']:

            referenced = graph[ref]
            if 'referees' not in referenced: referenced['referees'] = set()
            referenced['referees'].add(k)

    return graph

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

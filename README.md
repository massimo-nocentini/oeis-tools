# eois-tools

A suite of tools to interact with the [OEIS][oeis], providing both __console__
and __Jupyter notebook__ facilities. 

[oeis]:http://oeis.org/

A [talk][skku:talk] about them will be given at [SKKU AORC 2017][aorc].

[skku:talk]:http://massimo-nocentini.github.io/PhD/skku-aorc-2017/oeistools.html#/
[aorc]:http://shb.skku.edu/aorc/conference_info/new.jsp

## OEIS crawler

```
$ python3.6 crawling.py -h
usage: crawling.py [-h] [--clear-cache] [--restart] [--workers WORKERS]
                   [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                   [--cache-dir CACHE_DIR] [--progress-mark PROGRESS_MARK]
                   [S [S ...]]

OEIS Crawler.

positional arguments:
  S                     Sequence to fetch, given in the form Axxxxxx

optional arguments:
  -h, --help            show this help message and exit
  --clear-cache         Clear cache of sequences, according to --cache-dir
  --restart             Build fringe from cached sequences (defaults to False)
  --workers WORKERS     Degree of parallelism (defaults to 10)
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logger verbosity (defaults to ERROR)
  --cache-dir CACHE_DIR
                        Cache directory (defaults to ./fetched/)
  --progress-mark PROGRESS_MARK
                        Symbol for fetched event (defaults to ●)
```

## OEIS pprinter

The following is the help description of the console facility for the _pretty printer_; moreover,
a Jupyter notebook is also given ([view][pp:nb]).

[pp:nb]:http://nbviewer.jupyter.org/github/massimo-nocentini/oeis-tools/blob/master/notebooks/oeis-interaction.ipynb

```
$ python3.6 pprinting.py -h 
usage: pprinting.py [-h]
                    (--id ID | --seq SEQ | --query QUERY | --most-recents M)
                    [--force-fetch] [--cache-dir CACHE_DIR] [--tables-only]
                    [--start-index S] [--max-results R] [--data-only]
                    [--upper-limit U] [--comment-filter C]
                    [--formula-filter F] [--xrefs-filter X] [--link-filter L]
                    [--cite-filter R]

OEIS Pretty Printer.

optional arguments:
  -h, --help            show this help message and exit
  --id ID               Sequence id, given in the form Axxxxxx
  --seq SEQ             Literal sequence, ordered '[...]' or presence '{...}'
  --query QUERY         Open query for plain search, in the form '...'
  --most-recents M      Print the most recent sequences ranking by M in ACCESS
                        or MODIFY, looking into --cache-dir, at most --max-
                        results (defaults to None)
  --force-fetch         Bypass cache fetching again, according to --cache-dir
                        (defaults to False)
  --cache-dir CACHE_DIR
                        Cache directory (defaults to ./fetched/)
  --tables-only         Print matrix sequences only (defaults to False)
  --start-index S       Start from result at rank position S (defaults to 0)
  --max-results R       Pretty print the former R <= 10 results (defaults to
                        10)
  --data-only           Show only data repr and preamble (defaults to False)
  --upper-limit U       Upper limit for data repr: U is a dict '{"list":i,
                        "table":(r, c)}' where i, r and c are ints (defaults
                        to i=15, r=10 and c=10), respectively)
  --comment-filter C    Apply filter C to comments, where C is Python `lambda`
                        predicate 'lambda i,c: ...' referring to i-th comment
                        c
  --formula-filter F    Apply filter F to formulae, where F is Python `lambda`
                        predicate 'lambda i,f: ...' referring to i-th formula
                        f
  --xrefs-filter X      Apply filter X to cross refs, where X is Python
                        `lambda` predicate 'lambda i,x: ...' referring to i-th
                        xref x
  --link-filter L       Apply filter L to links, where L is Python `lambda`
                        predicate 'lambda i,l: ...' referring to i-th link l
  --cite-filter R       Apply filter R to citation, where R is Python `lambda`
                        predicate 'lambda i,r: ...' referring to i-th citation
                        r
```

## OEIS grapher

The following is the help description of the console facility for the _grapher_; moreover,
a Jupyter notebook is also given ([view][grapher:nb]).

[grapher:nb]:http://nbviewer.jupyter.org/github/massimo-nocentini/oeis-tools/blob/master/notebooks/oeis-mining.ipynb

```
$ python3.6 graphing.py -h 
usage: graphing.py [-h] [--directed] [--cache-dir CACHE_DIR]
                   [--graphs-dir GRAPHS_DIR] [--dpi DPI] [--layout LAYOUT]
                   F

OEIS grapher.

positional arguments:
  F                     Save image in file F.

optional arguments:
  -h, --help            show this help message and exit
  --directed            Draw directed edges
  --cache-dir CACHE_DIR
                        Cache directory (defaults to ./fetched/)
  --graphs-dir GRAPHS_DIR
                        Graphs directory (defaults to ./graphs/)
  --dpi DPI             Resolution in DPI (defaults to 600)
  --layout LAYOUT       Graph layout, choose from: {RANDOM, CIRCULAR, SHELL,
                        FRUCHTERMAN-REINGOLD, SPRING, SPECTRAL} (defaults to
                        SHELL)
```

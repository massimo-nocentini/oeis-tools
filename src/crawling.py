
import socket, json, re, os, sys, logging, asyncio, time

from contextlib import suppress
from functools import wraps, partial
from collections import namedtuple, deque
from itertools import count

from commons import Axxxxxx_regex, OEIS_sequenceid

# preamble {{{
logging.getLogger('asyncio').setLevel(logging.WARNING)

logging.basicConfig(level=logging.NOTSET)
logger = logging.getLogger(__name__)

Axxxxxx_regex = re.compile('(?P<id>A\d{6,6})')

URL = namedtuple('URL', ['host', 'port', 'resource'])
RestartingUrls = namedtuple('RestartingUrls', ['seen', 'fringe'])

loop = asyncio.get_event_loop()

#}}}

# reader, fetcher and crawler classes ________________________________________________________ {{{

class reader:

    def __init__(self, read):
        self.read = read

    def __aiter__(self):
        return self

    async def __anext__(self):
        chunk = await self.read()
        if chunk:   return chunk
        else:       raise StopAsyncIteration

class fetcher:

    def __init__(   self, url,
                    resource_key=lambda resource: resource,
                    done=lambda url, content: print(content)):

        self.url = url
        self.response = b''
        self.sock = None
        self.done = done
        self.resource_key=lambda: resource_key(self.url.resource)

    def encode_request(self, encoding='utf8'):

        request = 'GET {} HTTP/1.0\r\nHost: {}\r\n\r\n'.format(
                self.resource_key(), self.url.host)

        return request.encode(encoding)

    async def fetch(self):

        self.sock = socket.socket()
        self.sock.setblocking(False)

        await loop.sock_connect(self.sock, address=(self.url.host, self.url.port))            

        logger.info('Connection established with {} asking resource {}'.format(
                self.url.host, self.url.resource))

        await loop.sock_sendall(self.sock, self.encode_request())

        self.response = await self.read_all()

        self.sock.close()

        time.sleep(0.1)

        return self.done(self.url, self.response.decode('utf8'))

    async def read(self, nbytes=4096):

        chunk = await loop.sock_recv(self.sock, nbytes)
        return chunk

    async def read_all(self):

        response = [chunk async for chunk in reader(self.read)]
        return b''.join(response)


class crawler:

    def __init__(self, resources, fetcher_factory, max_tasks):

        self.resources = resources
        self.max_tasks = max_tasks
        self.fetcher_factory = fetcher_factory
        self.q = asyncio.Queue()

    async def crawl(self):

        for res in self.resources: self.q.put_nowait(res)

        tasks = [loop.create_task(coro=self.work()) for _ in range(self.max_tasks)]

        await self.q.join()
        
        for t in tasks: t.cancel()


    async def work(self):

        while True:

            resource = await self.q.get()

            await self.fetcher_factory(resource, appender=self.q.put_nowait).fetch()
            
            self.q.task_done()


#________________________________________________________________________________}}}

# OEIS stuff ____________________________________________________________________{{{


def cross_references(xref):
    return {r   for references in xref 
                for r in Axxxxxx_regex.findall(references)}

def make_resource(oeis_id):
    return r'/search?q=id%3A{}&fmt=json'.format(oeis_id)

def sets_of_cross_references(doc, sections=['xref']):
    sets = [cross_references(result.get(section, []))
            for result in doc.get('results', [])
            for section in sections]
    return sets

def parse_json( url, content, appender, seen_urls, 
                stubborn=False, progress_mark=None, cache_dir='./fetched/'):
    
    references = set()

    try:
        doc = json.loads(content[content.index('\n{'):])
        
        with open('{}{}.json'.format(cache_dir, url.resource), 'w') as f:
            json.dump(doc, f)
            f.flush()

        if progress_mark:
            print(progress_mark, end='', flush=True)
        
        seen_urls.add(url.resource)
        logger.info('fetched resource {}'.format(url.resource))

        references.update(*sets_of_cross_references(doc))
        
    except ValueError as e:
        message = 'Generic error for resource {}:\n{}\nRaw content: {}'
        logger.info(message.format(url.resource, e, content))
        if stubborn: references.add(url.resource)

    except json.JSONDecodeError as e:
        message = 'Decoding error for {}:\nException: {}\nRaw content: {}'
        logger.info(message.format(url.resource, e, content))
        if stubborn: references.add(url.resource)

    for ref in references - seen_urls:
        appender(ref)

def lookup_fetched_filenames(subdir): 
    return {filename[:filename.index('.json')]: subdir + filename 
            for filename in os.listdir(subdir) if filename.endswith('.json')}

def urls_in_cache(subdir):

    fetched_resources = lookup_fetched_filenames(subdir)

    seen_urls = set()
    initial_urls = set()

    for resource, filename in fetched_resources.items():

        with open(filename) as f:
            doc = json.loads(f.read())  

        # every resource with a attached file should be considered as an already seen urls
        seen_urls.add(resource) 

        # we consider its fringe as starting set of resources to fetch
        initial_urls.update(*sets_of_cross_references(doc))

    return RestartingUrls(seen=seen_urls, fringe=initial_urls-seen_urls)

def oeis(loop, initial_urls, workers, progress_mark, cache_dir):

    seen_urls = set()

    seen_urls.update(initial_urls.seen)

    logger.info('restarting with {} urls in the fringe, having fetched already {} resources.'.format(
            len(initial_urls.fringe), len(initial_urls.seen)))

    def factory(resource, appender):
        url = URL(host='oeis.org', port=80, resource=resource)
        kwds = {'appender': appender, 
                'seen_urls': seen_urls, 
                'progress_mark': progress_mark, 
                'cache_dir': cache_dir}
        return fetcher( url, done=partial(parse_json, **kwds), resource_key=make_resource)

    crawl_job = crawler(resources=initial_urls.fringe, 
                        fetcher_factory=factory, 
                        max_tasks=workers)

    with suppress(KeyboardInterrupt):
        loop.run_until_complete(crawl_job.crawl())

    fetched_urls = seen_urls - initial_urls.seen

    return fetched_urls

#________________________________________________________________________________}}}

# argument parsing {{{

def handle_cli_arguments():

    import argparse

    parser = argparse.ArgumentParser(description='OEIS Crawler.')

    parser.add_argument('sequences', metavar='S', nargs='*',
                        help='Sequence to fetch, given in the form Axxxxxx', type=OEIS_sequenceid)
    parser.add_argument("--clear-cache", help="Clear cache of sequences, according to --cache-dir", 
                        action="store_true")
    parser.add_argument("--restart", help="Build fringe from cached sequences (defaults to False)", 
                        action="store_true", default=False)
    parser.add_argument("--workers", help="Degree of parallelism (defaults to 10)", 
                        type=int, default=10)
    parser.add_argument("--log-level", help="Logger verbosity (defaults to ERROR)",
                        choices=['DEBUG','INFO','WARNING','ERROR','CRITICAL'], default='ERROR')
    parser.add_argument("--cache-dir", help="Cache directory (defaults to ./fetched/)",
                        default='./fetched/')
    parser.add_argument("--progress-mark", help="Symbol for fetched event (defaults to ●)", 
                        default='●')

    args = parser.parse_args()
    return args

# }}}

# main {{{

if __name__ == "__main__":

    args = handle_cli_arguments()

    cached_urls = urls_in_cache(subdir=args.cache_dir)

    if args.clear_cache:
        removed = 0
        for sequence in cached_urls.seen:
            filename = '{}{}.json'.format(args.cache_dir, sequence)
            os.remove(filename) 
            removed += 1

        print('{} sequences removed from cache {}'.format(removed, args.cache_dir))
        cached_urls.seen.clear()
        cached_urls.fringe.clear()

    logger.setLevel(args.log_level)

    if not args.sequences and not args.restart:
        print('{} sequences in cache {}\n{} sequences in fringe for restarting'.format(
            len(cached_urls.seen), args.cache_dir, len(cached_urls.fringe)))
    else:     
        if not args.restart:  
            cached_urls.fringe.clear()

        cached_urls.fringe.update(set(args.sequences))

        if not cached_urls.fringe.issubset(cached_urls.seen):
            fetched_urls = oeis(loop=loop, 
                                initial_urls=cached_urls, 
                                workers=args.workers,
                                progress_mark=args.progress_mark,
                                cache_dir=args.cache_dir)

            print('\nfetched {} new sequences:\n{}'.format(len(fetched_urls), fetched_urls))
        else:
            print('Fringe is a subset of fetched sequences, nothing to fetch')

# }}}    

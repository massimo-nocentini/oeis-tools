
import socket, json, re, os, sys

from contextlib import suppress
from selectors import DefaultSelector, EVENT_WRITE, EVENT_READ
from functools import wraps, partial
from collections import namedtuple, deque
from itertools import count
import logging

logging.basicConfig(level=logging.NOTSET)
logger = logging.getLogger(__name__)

OEIS_sequenceid_regex = re.compile('(?P<id>A\d{6,6})')

URL = namedtuple('URL', ['host', 'port', 'resource'])
RestartingUrls = namedtuple('RestartingUrls', ['seen', 'fringe'])

class CancelledError(BaseException): pass
class StopError(BaseException): pass

# future, task, queue and eventloop classes {{{

class reader:

    def __init__(self, read):
        self.read = read

    def __aiter__(self):
        return self

    async def __anext__(self):
        chunk = await self.read()
        if chunk:   return chunk
        else:       raise StopAsyncIteration

class pending:

    def __init__(self, handler):
        self.handler = handler

    async def __aenter__(self):

        f = future()
        self.handler(future=f)
        obj = await f
        return obj

    async def __aexit__(self, exc_type, exc, tb):
        pass


class future:
    ''' I represent some pending result that a coroutine is waiting for. '''

    def __init__(self):
        self.result = None
        self._callbacks = []

    def add_done_callbacks(self, callback):
        self._callbacks.append(callback)

    def resolve(self, value):
        self.result = value
        for c in self._callbacks: 
            c(resolved_future=self)

    def __await__(self):
        yield self
        return self.result

class task(future):

    def __init__(self, coro):
        future.__init__(self)
        self.coro = coro

    def start(self, *args, **kwds):
        return self(*args, resolved_future=future(), **kwds)

    def __call__(self, resolved_future, return_value=None, cancelled_value=None):
        try:
            pending_future = self.coro.send(resolved_future.result)
            pending_future.add_done_callbacks(self)
        except CancelledError as cancel:
            self.resolve(value=cancelled_value)
        except StopIteration as stop:
            self.resolve(value=getattr(stop, 'value', return_value))

    def cancel(self):
        self.coro.throw(CancelledError)

class queue(deque):

    def __init__(self, *args, **kwds):
        deque.__init__(self, *args, **kwds)
        self.join_future = future()
        self.unfinished_tasks = 0
        self.waiting_gets = []

    def put_nowait(self, item):
        self.unfinished_tasks += 1
        self.append(item)
        self._queue_not_empty_event() # fire the event

    def task_done(self):
        self.unfinished_tasks -= 1
        if not self.unfinished_tasks:
            self.join_future.resolve(value='no more items in queue')

    async def join(self):
        if self.unfinished_tasks:
            await self.join_future

    async def get(self):

        def item_available(future):
            self.waiting_gets.append(lambda: future.resolve(value=self.popleft()))

        async with pending(handler=item_available) as item:
            return item
            

    def _queue_not_empty_event(self):
        while self.waiting_gets and self:
            waiting_get = self.waiting_gets.pop()
            waiting_get()
        

class eventloop:

    def __init__(self, selector):
        self.selector = selector
        self.ticks = 0
        self.coro_result = None
        
    def _run_forever(self):
        while True:
            events = self.selector.select()
            self.ticks += 1
            for event_key, event_mask in events:
                callback = event_key.data
                callback(event_key, event_mask)

    def run_until_complete(self, coro):
        job = task(coro=coro)
        job.add_done_callbacks(callback=self._stop_eventhandler)
        job.start()
        with suppress(StopError):
            self._run_forever()
        return self.coro_result, self.ticks

    def _stop_eventhandler(self, resolved_future):
        self.coro_result = resolved_future.result
        raise StopError

#________________________________________________________________________________}}}

# fetcher and crawler classes ________________________________________________________ {{{

class fetcher:

    def __init__(   self, url, selector, 
                    resource_key=lambda resource: resource,
                    done=lambda url, content: print(content)):

        self.url = url
        self.selector = selector
        self.response = b''
        self.sock = None
        self.done = done
        self.resource_key=lambda: resource_key(self.url.resource)

    def encode_request(self, encoding='utf8'):

        request = 'GET {} HTTP/1.0\r\nHost: {}\r\n\r\n'.format(
                self.resource_key(), self.url.host)

        return request.encode(encoding)

    async def fetch(self):

        try:
            self.sock = socket.socket()
        except OSError as exc: # to catch 'Too many open files' exception
            logger.error('unable to make a new socket:\n{}'.format(exc))
            return

        self.sock.setblocking(False)

        with suppress(BlockingIOError):
            site = self.url.host, self.url.port
            try:
                self.sock.connect(site)
            except socket.gaierror as exc:
                logger.error('socket.connect fails on resource {}, discarding it'.format(self.url.resource))
                return
            
        def connection(future):

            def connected_eventhandler(event_key, event_mask):
                future.resolve(value='socket connected, ready for transmission')

            self.selector.register( self.sock.fileno(), 
                                    EVENT_WRITE, 
                                    connected_eventhandler)

        async with pending(handler=connection): pass

        self.selector.unregister(self.sock.fileno())

        logger.info('Connection established with {} asking resource {}'.format(
                self.url.host, self.url.resource))

        self.sock.send(self.encode_request())
        
        self.response = await self.read_all()
        
        self.sock.close()

        return self.done(self.url, self.response.decode('utf8'))

    async def read(self):

        def chunk_delivery(future):

            def readable_eventhandler(event_key, event_mask):
                future.resolve(value=self.sock.recv(4096))  # 4k chunk size.

            self.selector.register( self.sock.fileno(), 
                                    EVENT_READ, 
                                    readable_eventhandler)

        async with pending(handler=chunk_delivery) as chunk:
            selector.unregister(self.sock.fileno())
            return chunk


    async def read_all(self):

        response = [chunk async for chunk in reader(self.read)]

        return b''.join(response)

class crawler:

    def __init__(self, resources, fetcher_factory, max_tasks):

        self.resources = resources
        self.max_tasks = max_tasks
        self.fetcher_factory = fetcher_factory
        self.q = queue() 

    async def crawl(self):

        # If the workers were threads we might not wish to start them all at once. 
        # To avoid creating expensive threads until it is certain they are necessary, 
        # a thread pool typically grows on demand. But coroutines are cheap, so we 
        # simply start the maximum number allowed.
        workers = [task(coro=self.work()) for _ in range(self.max_tasks)]

        for w in workers: w.start()

        for res in self.resources: self.q.put_nowait(res)

        await self.q.join()

        for w in workers: w.cancel()


    async def work(self):

        while True:

            resource = await self.q.get()
            
            def appender(resource):
                if resource not in self.q: 
                    self.q.put_nowait(resource)

            await self.fetcher_factory(resource, appender).fetch()
            
            self.q.task_done()


#________________________________________________________________________________}}}

# OEIS stuff ____________________________________________________________________{{{


def cross_references(xref):
    return {r   for references in xref 
                for r in OEIS_sequenceid_regex.findall(references)}

def make_resource(oeis_id):
    return r'/search?q=id%3A{}&fmt=json'.format(oeis_id)

def sets_of_cross_references(doc, sections=['xref']):
    sets = [cross_references(result.get(section, []))
            for result in doc.get('results', [])
            for section in sections]
    return sets

def parse_json(url, content, appender, seen_urls, stubborn=False, progress_mark=None):
    
    references = set()

    try:
        doc = json.loads(content[content.index('\n{'):])
        
        with open('fetched/{}.json'.format(url.resource), 'w') as f:
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

def urls_in_cache(subdir):#, init, restart):

    fetched_resources = lookup_fetched_filenames(subdir)# if restart else {}

    seen_urls = set()
    initial_urls = set()

    for resource, filename in fetched_resources.items():

        with open(filename) as f:
            doc = json.loads(f.read())  

        # every resource with a attached file should be considered as an already seen urls
        seen_urls.add(resource) 

        # we consider its fringe as starting set of resources to fetch
        initial_urls.update(*sets_of_cross_references(doc))

    #initial_urls.update(init)

    return RestartingUrls(seen=seen_urls, fringe=initial_urls)

def oeis(loop, initial_urls, selector, workers, progress_mark):

    seen_urls = set()

    seen_urls.update(initial_urls.seen)

    logger.info('restarting with {} urls in the fringe, having fetched already {} resources.'.format(
            len(initial_urls.fringe), len(initial_urls.seen)))

    def factory(resource, appender):
        url = URL(host='oeis.org', port=80, resource=resource)
        kwds = {'appender': appender, 'seen_urls': seen_urls, 'progress_mark': progress_mark}
        return fetcher( url, selector, 
                        done=partial(parse_json, **kwds), 
                        resource_key=make_resource)

    crawl_job = crawler(resources=initial_urls.fringe, 
                        fetcher_factory=factory, max_tasks=workers)

    with suppress(KeyboardInterrupt):
        result, clock = loop.run_until_complete(crawl_job.crawl())

    fetched_urls = seen_urls - initial_urls.seen

    return fetched_urls

#________________________________________________________________________________}}}

# argument parsing {{{

def handle_cli_arguments():

    import argparse

    def OEIS_sequenceid(seqid):
        if not OEIS_sequenceid_regex.match(seqid):
            raise ValueError
        return seqid

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

    logger.setLevel(args.log_level)

    if not args.sequences and not args.restart:
        print('{} sequences in cache {}\n{} sequences in fringe for restarting'.format(
            len(cached_urls.seen), args.cache_dir, len(cached_urls.fringe)))
    else:     
        if not args.restart:  
            cached_urls.fringe.clear()

        cached_urls.fringe.update(set(args.sequences))

        if not cached_urls.fringe.issubset(cached_urls.seen):
            selector = DefaultSelector()
            fetched_urls = oeis(loop=eventloop(selector), 
                                initial_urls=cached_urls, 
                                selector=selector, 
                                workers=args.workers,
                                progress_mark=args.progress_mark)

            print('\nfetched {} new sequences:\n{}'.format(len(fetched_urls), fetched_urls))
        else:
            print('Fringe is a subset of fetched sequences, nothing to fetch')

    

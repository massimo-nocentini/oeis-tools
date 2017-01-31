
import re, requests

Axxxxxx_regex = re.compile('(?P<id>A\d{6,6})')

def fetch_oeis_payload( payload, 
                        then=None, 
                        network_error_handler=lambda exc: None, 
                        json_decoding_error_handler=lambda GET_result, exc: None, 
                        progress_indicator='●'):

    try: 
        GET_result = requests.get("https://oeis.org/search", params=payload,)
    except Exception as e: 
        return network_error_handler(e)

    try:
        doc = GET_result.json()

        if 'results' not in doc or not doc['results']: 
            doc['results'] = []

        if progress_indicator: 
            print(progress_indicator, end='')

    except Exception as e:
        return json_decoding_error_handler(e, GET_result)

    return then(doc, GET_result) if callable(then) else doc


def seqid_to_ahref(text):
    """
    Return a new string where each occurrence of a sequence ref `Axxxxxx` replaced as `<a href=...>` html tag.
    """
    return Axxxxxx_regex.sub(r'<a href="http://oeis.org/\g<id>">\g<id></a>', text)

# INTERFACES {{{

class interface:

    def dispatch(self, on, payload={}):
        message = self.select(on)
        return message(self, **payload)

    def selector(self, recv):
        raise ValueError('Cannot use `interface` abstract class as real object')

class notebook(interface):

    def select(self, recv):
        return recv.for_notebook

class console(interface):

    def select(self, recv):
        return recv.for_console

# }}}



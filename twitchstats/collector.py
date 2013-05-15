import pymongo
import requests
import json
import urlparse
import datetime
import copy
import uuid
import time
import pprint
import logbook

class CollectorError(Exception):
    """if something goes wrong use this"""

    def __init__(self, msg="n/a", **kw):
        self.msg = msg
        self.kw = kw

    def __repr__(self):
        return u"""<CollectorError: %s (%s)>""" %(self.msg, ", ".join(["%s:%s" %item for item in self.kw.items]))

class NetworkError(CollectorError):
    """subclass to mark network errors"""

class Resource(dict):
    """class for describing a JSON resource from the twitch API. It knows about all the metadata and can be used to e.g.
    retrieve the next set of items."""

    def __init__(self, url, client_id = "twitchstats v2", *args, **kwargs):
        """initialize the resource.

        :param url: the URL this resource stands for
        :param client_id: the client id to use to identify ourselves
        """
        super(Resource, self).__init__(*args, **kwargs)
        self.url = url
        self.client_id = client_id

        # fetch it
        self()

    def __call__(self):
        """fetch the resource"""

        # lets retrieve the data for this resource
        headers = {'Client-ID': self.client_id, 
                   'Accept' : 'application/vnd.twitchtv.v2+json'
        }
        attempts = 1
        while True:
            logbook.debug("fetching %s, attempt #%s" %(self.url, attempts))
            self.response = response = requests.get(self.url, headers = headers)
            if response.status_code == 200:
                break
            attempts = attempts + 1
            if attempts > 5:
                logbook.error("network error, code: %s" %response.status_code)
                raise NetworkError("network error, code != 200", code = response.status_code, url = self.url)
            time.sleep(4)
        self.clear()
        self.update(json.loads(response.text))
        self.links = self['_links']
        del self['_links']

    @property
    def has_next(self):
        """check if there is a next link available"""
        return "next" in self.links

    @property
    def next_batch(self):
        """retrieve the next batch"""
        url = self.links['next']
        return Resource(url, client_id = self.client_id)
        
class Collector(object):
    """class for collecting streaming statistics from twitch"""

    def __init__(self, 
            base_url="https://api.twitch.tv/kraken/", 
            mongodb_name="twitchstats",
            client_id = "twitchstats"):
        self.base_url = base_url
        self.mongodb_name = mongodb_name
        self.client_id = client_id

        self.db = pymongo.Connection()[self.mongodb_name]

    def _get(self, path):
        """retrieve a resource based on ``path``. We also put the client id into the header
        
        returns a JSONResponse Object which can be used to do additional requests

        """
        headers = {'Client-ID': self.client_id}
        if path.startswith("/"):
            path = path[1:]
        url = urlparse.urljoin(self.base_url, path)
        return Resource(url, client_id = self.client_id)


    def __call__(self):
        """run all collectors"""
        self.collect_summary()
        self.collect_games()
        self.collect_channels()

    def collect_summary(self):
        res = self._get("/streams/summary")
        res['date'] = datetime.datetime.now()
        self.db.summary.insert(res)
        logbook.debug("saving summary")

    def collect_channels(self):
        """retrieve the list of the top 99 streams and simply mark them as interesting streams to watch.

        What twitch returns is a list of streams associated with a channel. The difference is that a stream
        is one live session while the channel contains them. We will retrieve only channel information.
        
        """
        res = self._get("/streams?limit=99")
        inserts = []
        ok = True
        if len(res['streams']) == 0:
            logbook.error("list of streams is empty, aborting")
            ok = False
        for stream in res['streams']:
            channel = stream['channel']
            d = dict(
                _id = channel['_id'],
                name = channel['name'],
                display_name = channel['display_name'],
                url = channel['url'],
                logo = channel['logo'],
                created_at = channel['created_at'],
            )
            stream['date'] = datetime.datetime.now()
            stream['sid'] = stream['_id']
            stream['_id'] = unicode(uuid.uuid4())
            self.db.channels.save(d)            # this is the unique list of channels
            del stream['channel']['_links']    # remove links to make data more compact
            inserts.append(stream)
        if ok:
            logbook.debug("saving %s streams" %len(inserts))
            self.db.streams.insert(inserts)      # this is the snapshot of all streams every hour

    def collect_games(self):
        """get all games and their statistics
        """
        res = self._get("/games/top?limit=50")
        gameinfos = []
        ok = True
        while True:
            for game in res['top']:
                gameinfo = game['game']
                d = dict(
                    _id = gameinfo['_id'],
                    giantbomb_id = gameinfo['giantbomb_id'],
                    name = gameinfo['name'],
                    viewers = game['viewers'],
                    channels = game['channels'],
                    date = datetime.datetime.now(),
                )
                self.db.gamestats.insert(d)           # game statistics over time
                self.db.games.save(gameinfo)        
                gameinfos.append(gameinfo)
            if res['top'] == []:
                break
            if not res.has_next:
                break
            res = res.next_batch
        logbook.debug("finished collecting games, got %s" %len(gameinfos))


def collect():
    """collect stats"""

    error_handler = logbook.SyslogHandler('logbook example', level='ERROR', bubble=True)
    with error_handler.applicationbound():
        c = Collector("https://api.twitch.tv/kraken/")
        c()
    


        



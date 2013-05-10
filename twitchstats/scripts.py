from collector import Collector

def collect():
    c = Collector("https://api.twitch.tv/kraken/")
    c()

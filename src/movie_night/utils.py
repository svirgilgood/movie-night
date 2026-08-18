import hashlib
from pyoxigraph import (
    NamedNode
)
from dotenv import load_dotenv, dotenv_values
import os
import asyncio
import aiohttp

from typing import Dict

load_dotenv()

API_KEY = os.getenv("OMDBAPI_KEY")


class Namespace(str):
    def __new__(cls, value: str):
        return str.__new__(cls, value)

    def term(self, local: str) -> NamedNode:
        return NamedNode(self + local)

    def __getattr__(self, local: str) -> NamedNode:
        if local.startswith("__"):
            raise AttributeError
        return self.term(local)


class NS:
    def __init__(self, prefixes: Dict[str, str]):
        self.dict = prefixes

    def get(self, namespace):
        return Namespace(self.dict[namespace])

    def __getattr__(self, namespace):
        return self.get(namespace)


PREFIXES = {
    "mno": "https://ontology.movie-night.site/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}


ns = NS(PREFIXES)


async def auto_complete(partial_name: str):
    """
    query the OIMdb API to bring back a list of names that can be used for auto
    complete This needs to be made async
    """
    # print(partial_name)
    params = {"apikey": API_KEY, "s": partial_name}
    async with aiohttp.ClientSession() as session:
        async with session.get("http://www.omdbapi.com/",  params=params) as response:
            j = await response.json()
            return j
    # r = requests.get("http://www.omdbapi.com/", params=params)
    # return r.json()


def create_node(name: str, data_class="User") -> NamedNode:
    """
    Create a user based on the hash of the string
    """
    m = hashlib.sha256()
    m.update(name.encode("utf-8"))
    node = ns.mno.term(f"data/_{data_class}_" + m.hexdigest())
    return node

from pyoxigraph import (
    Store,
    NamedNode,
    Quad,
    Dataset,
    serialize,
    RdfFormat,
    parse,
    Literal,
    QuerySolutions,
    QueryResultsFormat,
    QueryBoolean,
    QueryTriples,
)
from dotenv import load_dotenv, dotenv_values
import os
from pathlib import Path
from .utils import ns, create_node

from typing import Dict

load_dotenv()
DATA_DIR = Path(os.getenv("DATA_DIR") or ".")

DB = DATA_DIR / "project.db"
store: Store = Store()


def create_database():
    """

    """
    global store

    if DB.exists():
        print("Loading existing store")
        store = Store(DB)
        print("store loaded")
    else:
        store = Store(DB)
        print("loading store from ttl")
        with open("movie-night.trig", "r") as ttlp:
            store.bulk_load(ttlp, format=RdfFormat.TRIG)
        print("store loaded")
        store.optimize()
        store.flush()
    return store

def get_user(username: str):
    query = """PREFIX mno:  <https://ontology.movie-night.site/>

    SELECT ?userNode ?userName ?fullName ?email ?hashedPassword ?disabled
    FROM %s
    WHERE {
        ?userNode
            mno:userName ?userName ;
            mno:fullName ?fullName ;
            mno:emailAddress ?email ;
            mno:hashedPassword ?hashedPassword ;
            mno:disabled ?disabled ;
        .
        VALUES ?userName { %s }
    }
    """ % (
        ns.mno.term("UserGraph"),
        Literal(username, datatype=ns.xsd.string),
    )
    results = store.query(query)
    if not isinstance(results, QuerySolutions):
        raise Exception("Mistake in Query")
    users = [
        {
            "user_node": res["userNode"].value,
            "username": res["userName"].value,
            "full_name": res["fullName"].value,
            "hashed_password": res["hashedPassword"].value,
            "email": res["email"].value,
            "disabled": res["disabled"].value,
        }
        for res in results
    ]

    if len(users) == 1:
        return users.pop()

def get_members(user_node: str):
    query = """PREFIX mno:  <https://ontology.movie-night.site/>

    SELECT ?member ?name (MAX(?date) AS ?lastDate)
    FROM %s
    WHERE {
        ?member
            a mno:Person ;
            mno:fullName ?name ;
            mno:choice [
                mno:onDate ?date ;
            ] ;
        .
    }
    GROUP BY ?member ?name
    ORDER BY ?lastDate

    """ % (NamedNode(user_node))
    #print(query)
    results = store.query(query)
    return [
        {
            "member": res["member"].value,
            "name": res["name"].value,
            "date": res["lastDate"].value,
        }
        for res in results
    ]

def add_family_member(user_node: str, new_family_member: str):
    """
    """
    new_node = create_node(new_family_member)
    query = """PREFIX mno:  <https://ontology.movie-night.site/>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    INSERT DATA {
        GRAPH %s {
            %s
                mno:fullName %s ;
                mno:choice [
                    mno:onDate "00-00-00T00:00:00.0000Z"^^xsd:dateTime ;
                ] ;
        }
    }
   """ % (NamedNode(user_node), new_node, Literal(new_family_member))

    store.update(query)


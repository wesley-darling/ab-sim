# ab_sim/runtime/resources.py
import pickle
from functools import lru_cache

# import networkx as nx


@lru_cache(maxsize=8)
def load_graph_from_path(file: str, fmt: str):
    if fmt == "pickle":
        with open(file, "rb") as f:
            return pickle.load(f)
    # if fmt == "graphml":
    #     return nx.read_graphml(file)
    # add other formats you support
    raise ValueError(f"Unsupported graph fmt {fmt!r}")

"""
Mini-Courier Planner  -  DAA Capstone (ETCCDA302)
Student : Shashank Sain   |   Roll No: 25013550023   |   B.Tech CSE (FSD)
K.R. Mangalam University, Gurugram

Pipeline
  1. Sort parcels by (deadline, -priority)         -> Merge Sort   O(n log n)
  2. Choose parcels for one trip                   -> 0/1 Knapsack O(n*W)   (Dynamic Programming)
  3. Shortest paths between delivery points        -> Dijkstra     O((V+E) log V)
  4. Overall delivery route                        -> Nearest-Neighbour TSP approximation O(k^2)
  5. Benchmark every step on growing input sizes and plot runtimes

Run:  python courier_planner.py                      (demo + benchmark + charts)
      python courier_planner.py data/your_file.json  (plan an unseen dataset)

JSON dataset format:
  {"edges": [[u, v, km], ...], "capacity": 20,
   "parcels": [{"pid":1,"dest":3,"weight":5,"priority":8,"deadline":6}, ...]}
"""
import heapq
import json
import random
import time
from dataclasses import dataclass

# ----------------------------------------------------------------------
# PHASE 1: DATA DESIGN
# ----------------------------------------------------------------------
@dataclass
class Parcel:
    pid: int          # unique parcel id
    dest: int         # graph node (customer location) where it must go
    weight: int       # kg  -> knapsack weight
    priority: int     # 1..10 -> knapsack value (higher = more important)
    deadline: int     # hours from now (smaller = more urgent)


# Graph format: adjacency list  {node: [(neighbour, distance_km), ...]}
# Node 0 is always the depot (courier hub).
def make_graph_from_edges(edges):
    g = {}
    for u, v, w in edges:           # undirected roads
        g.setdefault(u, []).append((v, w))
        g.setdefault(v, []).append((u, w))
    return g


# ----------------------------------------------------------------------
# PHASE 2a: SORTING (Merge Sort - stable, guaranteed O(n log n))
# ----------------------------------------------------------------------
def sort_key(p):
    """Earlier deadline first; ties broken by higher priority."""
    return (p.deadline, -p.priority)


def merge_sort(items, key=sort_key):
    if len(items) <= 1:
        return items
    mid = len(items) // 2
    left = merge_sort(items[:mid], key)
    right = merge_sort(items[mid:], key)
    merged, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if key(left[i]) <= key(right[j]):
            merged.append(left[i]); i += 1
        else:
            merged.append(right[j]); j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def insertion_sort(items, key=sort_key):
    """O(n^2) baseline, used only to compare against merge sort."""
    a = list(items)
    for i in range(1, len(a)):
        cur = a[i]
        j = i - 1
        while j >= 0 and key(a[j]) > key(cur):
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = cur
    return a


# ----------------------------------------------------------------------
# PHASE 2b: 0/1 KNAPSACK (Dynamic Programming)
# ----------------------------------------------------------------------
def knapsack(parcels, capacity):
    """
    dp[i][w] = best total priority using first i parcels with capacity w.
    Returns (best_value, chosen_parcels, dp_table).
    """
    n = len(parcels)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        wt, val = parcels[i - 1].weight, parcels[i - 1].priority
        for w in range(capacity + 1):
            dp[i][w] = dp[i - 1][w]                       # skip parcel i
            if wt <= w and dp[i - 1][w - wt] + val > dp[i][w]:
                dp[i][w] = dp[i - 1][w - wt] + val        # take parcel i
    # backtrack to find which parcels were taken
    chosen, w = [], capacity
    for i in range(n, 0, -1):
        if dp[i][w] != dp[i - 1][w]:
            chosen.append(parcels[i - 1])
            w -= parcels[i - 1].weight
    chosen.reverse()
    return dp[n][capacity], chosen, dp


# ----------------------------------------------------------------------
# PHASE 3a: DIJKSTRA
# ----------------------------------------------------------------------
def dijkstra(graph, source):
    """Returns (dist, prev) for all nodes reachable from source."""
    dist = {node: float("inf") for node in graph}
    prev = {node: None for node in graph}
    dist[source] = 0
    heap = [(0, source)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue                       # stale entry
        for v, w in graph[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))
    return dist, prev


def build_path(prev, target):
    path = []
    while target is not None:
        path.append(target)
        target = prev[target]
    return path[::-1]


# ----------------------------------------------------------------------
# PHASE 3b: NEAREST-NEIGHBOUR TSP APPROXIMATION
# ----------------------------------------------------------------------
def nearest_neighbour_route(graph, depot, stops):
    """
    Greedy tour: from the current location always go to the closest unvisited
    stop (distance = Dijkstra shortest path), finally return to the depot.
    Returns (stop_order, total_distance, full_node_path).
    """
    sp = {}                                   # cache one Dijkstra per needed node
    def info(u):
        if u not in sp:
            sp[u] = dijkstra(graph, u)
        return sp[u]

    unvisited = set(stops) - {depot}
    current, order, total = depot, [depot], 0
    full_path = [depot]
    while unvisited:
        dist, prev = info(current)
        nxt = min(unvisited, key=lambda s: dist[s])
        total += dist[nxt]
        full_path += build_path(prev, nxt)[1:]
        order.append(nxt)
        unvisited.remove(nxt)
        current = nxt
    dist, prev = info(current)                # return to depot
    total += dist[depot]
    full_path += build_path(prev, depot)[1:]
    order.append(depot)
    return order, total, full_path


# ----------------------------------------------------------------------
# DATA GENERATION
# ----------------------------------------------------------------------
def random_graph(n_nodes, extra_edges_factor=2, seed=1):
    """Connected random weighted graph: a random spanning tree + extra edges."""
    rnd = random.Random(seed)
    edges = set()
    for v in range(1, n_nodes):                       # spanning tree => connected
        u = rnd.randrange(v)
        edges.add((u, v, rnd.randint(1, 20)))
    for _ in range(n_nodes * extra_edges_factor):
        u, v = rnd.sample(range(n_nodes), 2)
        edges.add((min(u, v), max(u, v), rnd.randint(1, 20)))
    # keep only one weight per pair
    best = {}
    for u, v, w in edges:
        if (u, v) not in best or w < best[(u, v)]:
            best[(u, v)] = w
    return make_graph_from_edges([(u, v, w) for (u, v), w in best.items()])


def random_parcels(n, n_nodes, seed=1):
    rnd = random.Random(seed)
    return [Parcel(i + 1, rnd.randrange(1, n_nodes), rnd.randint(1, 15),
                   rnd.randint(1, 10), rnd.randint(1, 48)) for i in range(n)]


# ----------------------------------------------------------------------
# FULL PIPELINE
# ----------------------------------------------------------------------
def plan_delivery(parcels, graph, capacity, depot=0, verbose=False):
    timings = {}

    t = time.perf_counter()
    sorted_p = merge_sort(parcels)
    timings["Merge Sort"] = time.perf_counter() - t

    t = time.perf_counter()
    best_val, chosen, dp = knapsack(sorted_p, capacity)
    timings["Knapsack DP"] = time.perf_counter() - t

    stops = sorted({p.dest for p in chosen})
    t = time.perf_counter()
    order, total, path = nearest_neighbour_route(graph, depot, stops)
    timings["Dijkstra + NN-TSP"] = time.perf_counter() - t

    if verbose:
        print("Sorted parcels (pid, dest, kg, prio, deadline):")
        for p in sorted_p:
            print(f"  P{p.pid:<3} dest={p.dest:<2} {p.weight:>2}kg prio={p.priority:<2} deadline={p.deadline}h")
        print(f"\nKnapsack capacity = {capacity} kg  ->  best total priority = {best_val}")
        print("Selected parcels:", [f"P{p.pid}" for p in chosen],
              "| total weight =", sum(p.weight for p in chosen), "kg")
        print("\nDelivery stops order:", order)
        print("Full road path      :", path)
        print(f"Total route length  : {total} km")
    return sorted_p, chosen, best_val, order, total, path, timings


# ----------------------------------------------------------------------
# PHASE 2/3 DEMO ON SMALL, TRACEABLE DATASET
# ----------------------------------------------------------------------
def demo():
    edges = [(0, 1, 4), (0, 2, 2), (1, 2, 1), (1, 3, 5), (2, 3, 8), (2, 4, 10),
             (3, 4, 2), (3, 5, 6), (4, 5, 3), (0, 6, 7), (5, 6, 4)]
    graph = make_graph_from_edges(edges)
    parcels = [Parcel(1, 3, 5, 8, 6), Parcel(2, 5, 8, 6, 3), Parcel(3, 1, 3, 4, 10),
               Parcel(4, 4, 6, 9, 3), Parcel(5, 6, 4, 5, 12), Parcel(6, 2, 7, 7, 5)]
    print("=" * 60, "\nSMALL DEMO DATASET (7 nodes, 6 parcels, capacity 20 kg)\n" + "=" * 60)
    plan_delivery(parcels, graph, capacity=20, verbose=True)

    # Dijkstra evidence from depot
    dist, prev = dijkstra(graph, 0)
    print("\nDijkstra from depot 0:")
    for v in sorted(dist):
        print(f"  0 -> {v}: {dist[v]:>2} km via {build_path(prev, v)}")

    with open("data/sample_small.json", "w") as f:
        json.dump({"edges": edges, "capacity": 20,
                   "parcels": [p.__dict__ for p in parcels]}, f, indent=2)


# ----------------------------------------------------------------------
# LOAD AN EXTERNAL DATASET (for unseen-data demonstration / viva)
# ----------------------------------------------------------------------
def load_dataset(path):
    with open(path) as f:
        data = json.load(f)
    graph = make_graph_from_edges([tuple(e) for e in data["edges"]])
    parcels = [Parcel(**p) for p in data["parcels"]]
    for p in parcels:
        if p.dest not in graph:
            raise ValueError(f"Parcel {p.pid}: destination {p.dest} is not in the graph")
    return graph, parcels, data["capacity"]


# ----------------------------------------------------------------------
# PHASE 4: BENCHMARKS + CHARTS
# ----------------------------------------------------------------------
def timeit(fn, *args, repeat=3):
    best = float("inf")
    for _ in range(repeat):
        t = time.perf_counter()
        r = fn(*args)
        best = min(best, time.perf_counter() - t)
    return best, r


def benchmark():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sizes = [50, 100, 200, 400, 800, 1600]
    cap = 100
    rows = []
    print("\n" + "=" * 60, "\nBENCHMARK\n" + "=" * 60)
    print(f"{'n':>6} {'merge(s)':>10} {'insert(s)':>10} {'knap(s)':>10} {'route(s)':>10} {'check':>6}")
    for n in sizes:
        nodes = max(20, n // 2)
        g = random_graph(nodes)
        ps = random_parcels(n, nodes)
        t_merge, s1 = timeit(merge_sort, ps)
        t_ins, s2 = timeit(insertion_sort, ps) if n <= 1600 else (float("nan"), s1)
        t_knap, (val, chosen, _) = timeit(knapsack, s1, cap)
        stops = sorted({p.dest for p in chosen})
        t_route, (order, total, _) = timeit(nearest_neighbour_route, g, 0, stops, repeat=1)

        # correctness checks
        ok = (s1 == sorted(ps, key=sort_key)
              and [sort_key(p) for p in s1] == [sort_key(p) for p in s2]
              and sum(p.weight for p in chosen) <= cap
              and sum(p.priority for p in chosen) == val)
        rows.append((n, t_merge, t_ins, t_knap, t_route, ok))
        print(f"{n:>6} {t_merge:>10.5f} {t_ins:>10.5f} {t_knap:>10.5f} {t_route:>10.5f} {str(ok):>6}")

    ns = [r[0] for r in rows]
    # Chart 1: sorting comparison
    plt.figure(figsize=(7, 4.5))
    plt.plot(ns, [r[1] for r in rows], "o-", label="Merge sort  O(n log n)")
    plt.plot(ns, [r[2] for r in rows], "s-", label="Insertion sort  O(n²)")
    plt.xlabel("Number of parcels"); plt.ylabel("Runtime (s)")
    plt.title("Sorting runtime comparison"); plt.legend(); plt.grid(alpha=.3)
    plt.tight_layout(); plt.savefig("runtime_sorting.png", dpi=150); plt.close()

    # Chart 2: major steps
    plt.figure(figsize=(7, 4.5))
    plt.plot(ns, [r[1] for r in rows], "o-", label="Merge sort")
    plt.plot(ns, [r[3] for r in rows], "s-", label="Knapsack DP (W=100)")
    plt.plot(ns, [r[4] for r in rows], "^-", label="Dijkstra + NN-TSP")
    plt.yscale("log")
    plt.xlabel("Number of parcels"); plt.ylabel("Runtime (s, log scale)")
    plt.title("Runtime of major pipeline steps"); plt.legend(); plt.grid(alpha=.3, which="both")
    plt.tight_layout(); plt.savefig("runtime_pipeline.png", dpi=150); plt.close()
    print("\nCharts saved: runtime_sorting.png, runtime_pipeline.png")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:                      # unseen dataset mode
        g, ps, cap = load_dataset(sys.argv[1])
        print(f"Loaded {len(ps)} parcels, {len(g)} nodes, capacity {cap} kg\n")
        plan_delivery(ps, g, cap, verbose=True)
    else:
        demo()
        benchmark()

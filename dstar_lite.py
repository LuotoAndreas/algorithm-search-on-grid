import heapq
import math
import time

from algorithms import manhattan_distance


class DStarLite:
    """
    D* Lite -algoritmin ruudukkopohjainen toteutus optimoiduilla 2D-taulukoilla.
    """

    def __init__(self, grid, start, goal):
        self.grid = grid
        self.start = start
        self.goal = goal
        
        # Haetaan ruudukon koko grid-oliolta
        self.height = getattr(grid, "height", getattr(grid, "rows", None))
        self.width = getattr(grid, "width", getattr(grid, "cols", None))

        if self.height is None or self.width is None:
            raise ValueError("Grid-luokasta ei löytynyt height/width- tai rows/cols-arvoja.")

        self.k_m = 0
        self.last_start = start

        # 1. OPTIMOINTI: Esilasketaan naapurit, jotta vältetään listojen luominen lennossa
        self.all_neighbors_cache = {}
        for r in range(self.height):
            for c in range(self.width):
                neighbors = []
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    if grid.in_bounds(r + dr, c + dc):
                        neighbors.append((r + dr, c + dc))
                self.all_neighbors_cache[(r, c)] = neighbors

        # Alustetaan tyhjät rakenteet (initialize täyttää g- ja rhs-taulukot)
        self.open_list = []
        self.open_entries = {}
        self.visited_order = []
        self.g = []
        self.rhs = []

        self.initialize()

    def get_g(self, node):
        r, c = node
        return self.g[r][c]

    def get_rhs(self, node):
        r, c = node
        return self.rhs[r][c]

    def set_g(self, node, value):
        r, c = node
        self.g[r][c] = value

    def set_rhs(self, node, value):
        r, c = node
        self.rhs[r][c] = value

    def calculate_key(self, node):
        min_g_rhs = min(self.get_g(node), self.get_rhs(node))
        return (
            min_g_rhs + manhattan_distance(self.start, node) + self.k_m,
            min_g_rhs
        )

    def initialize(self):
        """
        Alustaa D* Lite -algoritmin rakenteet ja 2D-taulukot.
        """
        self.open_list = []
        self.open_entries = {}
        self.visited_order = []

        # KORJAUS: Alustetaan 2D-taulukot suoraan täällä math.inf-arvoilla
        self.g = [[math.inf for _ in range(self.width)] for _ in range(self.height)]
        self.rhs = [[math.inf for _ in range(self.width)] for _ in range(self.height)]

        self.set_rhs(self.goal, 0)
        self.insert_or_update(self.goal)

    def insert_or_update(self, node):
        key = self.calculate_key(node)
        self.open_entries[node] = key
        heapq.heappush(self.open_list, (key, node))

    def remove_from_open(self, node):
        if node in self.open_entries:
            del self.open_entries[node]

    def remove_invalid_open_entries(self):
        while self.open_list:
            key, node = self.open_list[0]
            if node in self.open_entries and self.open_entries[node] == key:
                break
            heapq.heappop(self.open_list)

    def top_key(self):
        self.remove_invalid_open_entries()
        if not self.open_list:
            return (math.inf, math.inf)
        return self.open_list[0][0]

    def cost(self, from_node, to_node):
        row, col = to_node
        if self.grid.is_obstacle(row, col):
            return math.inf
        return 1

    def get_all_neighbors(self, node):
        # 2. OPTIMOINTI: Palautetaan valmis lista välimuistista O(1)-ajassa
        return self.all_neighbors_cache[node]

    def get_successors(self, node):
        return self.get_all_neighbors(node)

    def get_predecessors(self, node):
        return self.get_all_neighbors(node)

    def update_vertex(self, node):
        if node != self.goal:
            best_rhs = math.inf
            for successor in self.get_successors(node):
                candidate_rhs = self.cost(node, successor) + self.get_g(successor)
                if candidate_rhs < best_rhs:
                    best_rhs = candidate_rhs
            self.set_rhs(node, best_rhs)

        self.remove_from_open(node)
        if self.get_g(node) != self.get_rhs(node):
            self.insert_or_update(node)

    def compute_shortest_path(self, reset_visited=True):
        if reset_visited:
            self.visited_order = []

        while (
            self.top_key() < self.calculate_key(self.start)
            or self.get_rhs(self.start) != self.get_g(self.start)
        ):
            self.remove_invalid_open_entries()
            if not self.open_list:
                break

            old_key, current = heapq.heappop(self.open_list)
            if current not in self.open_entries:
                continue

            del self.open_entries[current]
            new_key = self.calculate_key(current)

            if old_key < new_key:
                self.insert_or_update(current)
            elif self.get_g(current) > self.get_rhs(current):
                self.set_g(current, self.get_rhs(current))
                self.visited_order.append(current)

                for predecessor in self.get_predecessors(current):
                    self.update_vertex(predecessor)
            else:
                self.set_g(current, math.inf)
                self.visited_order.append(current)

                affected_nodes = list(self.get_predecessors(current))
                affected_nodes.append(current)

                for predecessor in affected_nodes:
                    self.update_vertex(predecessor)

    def get_path(self):
        if self.get_rhs(self.start) == math.inf:
            return []

        path = [self.start]
        current = self.start
        visited_in_path = set()

        while current != self.goal:
            if current in visited_in_path:
                return []
            visited_in_path.add(current)

            best_neighbor = None
            best_cost = math.inf

            for neighbor in self.get_successors(current):
                candidate_cost = self.cost(current, neighbor) + self.get_g(neighbor)
                if candidate_cost < best_cost:
                    best_cost = candidate_cost
                    best_neighbor = neighbor

            if best_neighbor is None or best_cost == math.inf:
                return []

            current = best_neighbor
            path.append(current)

        return path

    def move_start(self, new_start):
        self.k_m += manhattan_distance(self.last_start, new_start)
        self.last_start = new_start
        self.start = new_start

    def update_obstacle(self, obstacle_position):
        affected_nodes = list(self.get_predecessors(obstacle_position))
        affected_nodes.append(obstacle_position)

        for node in affected_nodes:
            self.update_vertex(node)

    def get_current_result(self, calculation_time):
        path = self.get_path()
        return {
            "algorithm": "D* Lite",
            "path": path,
            "visited_order": list(self.visited_order),
            "calculation_time": calculation_time,
            "visited_count": len(self.visited_order),
            "path_length": max(0, len(path) - 1),
            "success": len(path) > 0,
        }


def dstar_lite_search(grid, start, goal):
    start_time = time.perf_counter()

    planner = DStarLite(grid, start, goal)
    planner.compute_shortest_path(reset_visited=True)
    path = planner.get_path()

    end_time = time.perf_counter()

    result = {
        "algorithm": "D* Lite",
        "path": path,
        "visited_order": planner.visited_order,
        "calculation_time": end_time - start_time,
        "visited_count": len(planner.visited_order),
        "path_length": max(0, len(path) - 1),
        "success": len(path) > 0,
    }

    return result
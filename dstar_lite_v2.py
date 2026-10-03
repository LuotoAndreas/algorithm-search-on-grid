"""Correctly notified, instrumented D* Lite for the final-v2 experiment."""

from __future__ import annotations

import heapq
import math

from algorithms_v2 import GridState, Node, SearchResult, WorkMetrics, manhattan


class DStarLiteV2:
    def __init__(self, grid: GridState, start: Node, goal: Node, collect_work: bool = True):
        self.grid = grid
        self.start = start
        self.goal = goal
        self.last_start = start
        self.km = 0
        self.collect_work = collect_work
        self.g = {node: math.inf for node in grid.roads}
        self.rhs = {node: math.inf for node in grid.roads}
        self.rhs[goal] = 0
        self.open_heap: list[tuple[tuple[float, float], Node]] = []
        self.open_entries: dict[Node, tuple[float, float]] = {}
        self.work = WorkMetrics()
        self._insert(goal)

    def reset_episode_metrics(self) -> None:
        self.work = WorkMetrics()

    def _key(self, node: Node) -> tuple[float, float]:
        value = min(self.g[node], self.rhs[node])
        return value + manhattan(self.start, node) + self.km, value

    def _insert(self, node: Node) -> None:
        key = self._key(node)
        self.open_entries[node] = key
        heapq.heappush(self.open_heap, (key, node))

    def _remove(self, node: Node) -> None:
        self.open_entries.pop(node, None)

    def _discard_stale(self) -> None:
        while self.open_heap:
            key, node = self.open_heap[0]
            if self.open_entries.get(node) == key:
                return
            heapq.heappop(self.open_heap)
            if self.collect_work:
                self.work.stale_queue_pop_events += 1

    def _top_key(self) -> tuple[float, float]:
        self._discard_stale()
        return self.open_heap[0][0] if self.open_heap else (math.inf, math.inf)

    def _cost(self, _from_node: Node, to_node: Node) -> float:
        return math.inf if not self.grid.is_open(to_node) else 1

    def _update_vertex(self, node: Node) -> None:
        if node != self.goal:
            best = math.inf
            for successor in self.grid.adjacency[node]:
                if self.collect_work:
                    self.work.neighbor_evaluation_events += 1
                best = min(best, self._cost(node, successor) + self.g[successor])
            self.rhs[node] = best
        self._remove(node)
        if self.g[node] != self.rhs[node]:
            self._insert(node)

    def compute_shortest_path(self) -> None:
        while self._top_key() < self._key(self.start) or self.rhs[self.start] != self.g[self.start]:
            self._discard_stale()
            if not self.open_heap:
                break
            old_key, current = heapq.heappop(self.open_heap)
            if self.open_entries.get(current) != old_key:
                if self.collect_work:
                    self.work.stale_queue_pop_events += 1
                continue
            del self.open_entries[current]
            if self.collect_work:
                self.work.valid_queue_pop_events += 1
            new_key = self._key(current)
            if old_key < new_key:
                self._insert(current)
                continue
            if self.collect_work:
                self.work.expansion_events += 1
                self.work.expanded_cells.add(current)
            if self.g[current] > self.rhs[current]:
                self.g[current] = self.rhs[current]
                for predecessor in self.grid.adjacency[current]:
                    self._update_vertex(predecessor)
            else:
                self.g[current] = math.inf
                for predecessor in (*self.grid.adjacency[current], current):
                    self._update_vertex(predecessor)

    def move_start(self, new_start: Node) -> None:
        self.km += manhattan(self.last_start, new_start)
        self.last_start = new_start
        self.start = new_start

    def notify_changed_cell(self, cell: Node) -> None:
        """Report every cell-cost change after the grid state has been changed."""
        for predecessor in (*self.grid.adjacency[cell], cell):
            self._update_vertex(predecessor)

    def get_path(self) -> list[Node]:
        if self.rhs[self.start] == math.inf:
            return []
        path = [self.start]
        current = self.start
        seen: set[Node] = set()
        while current != self.goal:
            if current in seen:
                return []
            seen.add(current)
            best_node = None
            best_key = (math.inf, (math.inf, math.inf))
            for neighbor in self.grid.adjacency[current]:
                if self.collect_work:
                    self.work.path_neighbor_evaluation_events += 1
                candidate = self._cost(current, neighbor) + self.g[neighbor]
                # Coordinate is a deterministic secondary choice only.
                key = (candidate, neighbor)
                if key < best_key:
                    best_key = key
                    best_node = neighbor
            if best_node is None or best_key[0] == math.inf:
                return []
            current = best_node
            path.append(current)
            if self.collect_work:
                self.work.path_reconstruction_steps += 1
        return path

    def result(self) -> SearchResult:
        path = self.get_path()
        return SearchResult(
            algorithm="D* Lite",
            path=path,
            distance=len(path) - 1 if path else None,
            success=bool(path),
            work=self.work,
        )

    def initial_search(self) -> SearchResult:
        self.reset_episode_metrics()
        self.compute_shortest_path()
        return self.result()

    def apply_changed_cell(self, cell: Node) -> SearchResult:
        self.reset_episode_metrics()
        self.notify_changed_cell(cell)
        self.compute_shortest_path()
        return self.result()

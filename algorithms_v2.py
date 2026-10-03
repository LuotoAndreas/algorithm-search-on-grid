"""Instrumented shortest-path algorithms for the final-v2 experiment."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import heapq
import math
from typing import Iterable


Node = tuple[int, int]
NEIGHBOR_DELTAS = ((-1, 0), (0, -1), (0, 1), (1, 0))


@dataclass
class WorkMetrics:
    expansion_events: int = 0
    valid_queue_pop_events: int = 0
    stale_queue_pop_events: int = 0
    neighbor_evaluation_events: int = 0
    path_reconstruction_steps: int = 0
    path_neighbor_evaluation_events: int = 0
    expanded_cells: set[Node] = field(default_factory=set)

    @property
    def unique_expanded_cells(self) -> int:
        return len(self.expanded_cells)

    def to_dict(self) -> dict[str, int]:
        return {
            "expansion_events": self.expansion_events,
            "unique_expanded_cells": self.unique_expanded_cells,
            "valid_queue_pop_events": self.valid_queue_pop_events,
            "stale_queue_pop_events": self.stale_queue_pop_events,
            "neighbor_evaluation_events": self.neighbor_evaluation_events,
            "path_reconstruction_steps": self.path_reconstruction_steps,
            "path_neighbor_evaluation_events": self.path_neighbor_evaluation_events,
        }


@dataclass
class SearchResult:
    algorithm: str
    path: list[Node]
    distance: int | None
    success: bool
    work: WorkMetrics


class GridState:
    """A fixed road graph plus a mutable set of closed road cells."""

    def __init__(
        self,
        rows: int,
        cols: int,
        roads: Iterable[Node],
        blocked: Iterable[Node] = (),
    ):
        self.rows = rows
        self.cols = cols
        self.roads = frozenset(roads)
        self.blocked = set(blocked)
        self.adjacency = {
            node: tuple(
                neighbor
                for dr, dc in NEIGHBOR_DELTAS
                if (neighbor := (node[0] + dr, node[1] + dc)) in self.roads
            )
            for node in self.roads
        }

    def clone(self) -> "GridState":
        clone = object.__new__(GridState)
        clone.rows = self.rows
        clone.cols = self.cols
        clone.roads = self.roads
        clone.blocked = set(self.blocked)
        clone.adjacency = self.adjacency
        return clone

    def block(self, node: Node) -> None:
        if node not in self.roads:
            raise ValueError(f"Cannot block non-road cell {node}.")
        self.blocked.add(node)

    def is_open(self, node: Node) -> bool:
        return node in self.roads and node not in self.blocked

    def neighbors(self, node: Node) -> tuple[Node, ...]:
        return tuple(n for n in self.adjacency.get(node, ()) if n not in self.blocked)


def manhattan(a: Node, b: Node) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def reconstruct_path(
    previous: dict[Node, Node],
    start: Node,
    goal: Node,
    metrics: WorkMetrics,
    collect_work: bool,
) -> list[Node]:
    if start == goal:
        return [start]
    if goal not in previous:
        return []
    path = [goal]
    current = goal
    while current != start:
        current = previous[current]
        path.append(current)
        if collect_work:
            metrics.path_reconstruction_steps += 1
    path.reverse()
    return path


def canonical_bfs(grid: GridState, start: Node, goal: Node) -> list[Node]:
    """Untimed experimental oracle with a fixed neighbour order."""
    if not grid.is_open(start) or not grid.is_open(goal):
        return []
    queue = deque([start])
    previous: dict[Node, Node] = {}
    seen = {start}
    while queue:
        current = queue.popleft()
        if current == goal:
            metrics = WorkMetrics()
            return reconstruct_path(previous, start, goal, metrics, False)
        for neighbor in grid.neighbors(current):
            if neighbor not in seen:
                seen.add(neighbor)
                previous[neighbor] = current
                queue.append(neighbor)
    return []


def _best_first_search(
    algorithm: str,
    grid: GridState,
    start: Node,
    goal: Node,
    use_heuristic: bool,
    collect_work: bool,
) -> SearchResult:
    metrics = WorkMetrics()
    if not grid.is_open(start) or not grid.is_open(goal):
        return SearchResult(algorithm, [], None, False, metrics)

    queue: list[tuple[int, int, Node]] = []
    serial = 0
    heapq.heappush(queue, (manhattan(start, goal) if use_heuristic else 0, serial, start))
    distance = {start: 0}
    previous: dict[Node, Node] = {}
    closed: set[Node] = set()

    while queue:
        priority, _, current = heapq.heappop(queue)
        expected = distance.get(current, math.inf) + (manhattan(current, goal) if use_heuristic else 0)
        if current in closed or priority != expected:
            if collect_work:
                metrics.stale_queue_pop_events += 1
            continue
        if collect_work:
            metrics.valid_queue_pop_events += 1
            metrics.expansion_events += 1
            metrics.expanded_cells.add(current)
        closed.add(current)
        if current == goal:
            break
        for neighbor in grid.neighbors(current):
            if collect_work:
                metrics.neighbor_evaluation_events += 1
            tentative = distance[current] + 1
            if tentative < distance.get(neighbor, math.inf):
                distance[neighbor] = tentative
                previous[neighbor] = current
                serial += 1
                estimate = tentative + (manhattan(neighbor, goal) if use_heuristic else 0)
                heapq.heappush(queue, (estimate, serial, neighbor))

    path = reconstruct_path(previous, start, goal, metrics, collect_work)
    return SearchResult(
        algorithm=algorithm,
        path=path,
        distance=len(path) - 1 if path else None,
        success=bool(path),
        work=metrics,
    )


def dijkstra_v2(
    grid: GridState,
    start: Node,
    goal: Node,
    collect_work: bool = True,
) -> SearchResult:
    return _best_first_search("Dijkstra", grid, start, goal, False, collect_work)


def astar_v2(
    grid: GridState,
    start: Node,
    goal: Node,
    collect_work: bool = True,
) -> SearchResult:
    return _best_first_search("A*", grid, start, goal, True, collect_work)


def validate_path(grid: GridState, path: list[Node], start: Node, goal: Node) -> tuple[bool, str]:
    if not path:
        return False, "empty_path"
    if path[0] != start:
        return False, "wrong_start"
    if path[-1] != goal:
        return False, "wrong_goal"
    for node in path:
        if not grid.is_open(node):
            return False, f"blocked_or_nonroad_cell:{node}"
    for first, second in zip(path, path[1:]):
        if manhattan(first, second) != 1:
            return False, f"non_adjacent_step:{first}->{second}"
    return True, "ok"

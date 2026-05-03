import heapq
import time


def reconstruct_path(previous, start, goal):
    """
    Muodostaa lopullisen reitin previous-sanakirjan perusteella.

    previous kertoo, mistä ruudusta kuhunkin ruutuun on tultu.
    Kun kohde löytyy, reitti voidaan rakentaa kulkemalla kohteesta
    takaisin lähtöön ja kääntämällä lopputulos.
    """
    path = []
    current = goal

    while current != start:
        path.append(current)

        if current not in previous:
            return []

        current = previous[current]

    path.append(start)
    path.reverse()

    return path


def manhattan_distance(a, b):
    """
    Manhattan-etäisyys ruudukossa.

    Tätä käytetään A*-algoritmin heuristiikkana.
    Se sopii tilanteeseen, jossa liikkuminen on sallittu vain neljään suuntaan:
    ylös, alas, vasemmalle ja oikealle.
    """
    row_a, col_a = a
    row_b, col_b = b

    return abs(row_a - row_b) + abs(col_a - col_b)


def dijkstra(grid, start, goal):
    """
    Dijkstran algoritmi ruudukossa.

    Perusidea:
    - Jokaiselle ruudulle pidetään kirjaa halvimmasta tunnetusta kustannuksesta.
    - Aluksi lähtöruudun kustannus on 0.
    - Aina käsitellään se ruutu, johon tunnettu kustannus on pienin.
    - Naapureille tarjotaan uutta kustannusta nykyisen ruudun kautta.
    - Jos uusi kustannus on aiempaa parempi, se tallennetaan.

    Koska jokaisen siirtymän kustannus on tässä vaiheessa 1,
    reitin kustannus vastaa askelten määrää.
    """

    start_time = time.perf_counter()

    priority_queue = []
    heapq.heappush(priority_queue, (0, start))

    distance = {start: 0}
    previous = {}
    visited_order = []
    visited = set()

    while priority_queue:
        current_distance, current = heapq.heappop(priority_queue)

        if current in visited:
            continue

        visited.add(current)
        visited_order.append(current)

        if current == goal:
            break

        for neighbor in grid.get_neighbors(current):
            movement_cost = 1
            new_distance = current_distance + movement_cost

            if neighbor not in distance or new_distance < distance[neighbor]:
                distance[neighbor] = new_distance
                previous[neighbor] = current
                heapq.heappush(priority_queue, (new_distance, neighbor))

    path = reconstruct_path(previous, start, goal)
    end_time = time.perf_counter()

    result = {
        "algorithm": "Dijkstra",
        "path": path,
        "visited_order": visited_order,
        "calculation_time": end_time - start_time,
        "visited_count": len(visited_order),
        "path_length": max(0, len(path) - 1),
        "success": len(path) > 0,
    }

    return result


def astar(grid, start, goal):
    """
    A*-algoritmi ruudukossa.

    Perusidea:
    - Kuten Dijkstra, A* seuraa halvinta tunnettua kuljettua kustannusta.
    - Lisäksi se arvioi, kuinka paljon matkaa on jäljellä kohteeseen.
    - Seuraavaksi käsiteltävä ruutu valitaan arvolla:

          f(n) = g(n) + h(n)

      missä:
      g(n) = kuljettu kustannus lähtöruudusta ruutuun n
      h(n) = heuristinen arvio ruudusta n kohteeseen

    Tässä h(n) on Manhattan-etäisyys.
    """

    start_time = time.perf_counter()

    priority_queue = []

    start_g_cost = 0
    start_h_cost = manhattan_distance(start, goal)
    start_f_cost = start_g_cost + start_h_cost

    heapq.heappush(priority_queue, (start_f_cost, start))

    # g_cost kertoo todellisen tunnetun kustannuksen lähtöpisteestä ruutuun.
    g_cost = {start: 0}

    previous = {}
    visited_order = []
    visited = set()

    while priority_queue:
        current_f_cost, current = heapq.heappop(priority_queue)

        if current in visited:
            continue

        visited.add(current)
        visited_order.append(current)

        if current == goal:
            break

        for neighbor in grid.get_neighbors(current):
            movement_cost = 1
            tentative_g_cost = g_cost[current] + movement_cost

            if neighbor not in g_cost or tentative_g_cost < g_cost[neighbor]:
                g_cost[neighbor] = tentative_g_cost
                previous[neighbor] = current

                h_cost = manhattan_distance(neighbor, goal)
                f_cost = tentative_g_cost + h_cost

                heapq.heappush(priority_queue, (f_cost, neighbor))

    path = reconstruct_path(previous, start, goal)
    end_time = time.perf_counter()

    result = {
        "algorithm": "A*",
        "path": path,
        "visited_order": visited_order,
        "calculation_time": end_time - start_time,
        "visited_count": len(visited_order),
        "path_length": max(0, len(path) - 1),
        "success": len(path) > 0,
    }

    return result
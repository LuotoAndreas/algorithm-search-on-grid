import pygame
import sys
import time

from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    CELL_SIZE,
    WHITE,
    LIGHT_GRAY,
    BLACK,
    GREEN,
    RED,
    BLUE,
    YELLOW,
    ORANGE,
    DARK_GRAY,
    VISITED_ANIMATION_DELAY_MS,
    PATH_ANIMATION_DELAY_MS,
    VEHICLE_MOVE_DELAY_MS,
)
from grid import Grid
from algorithms import dijkstra, astar
from dstar_lite import DStarLite, dstar_lite_search
from metrics import SimulationMetrics


def mouse_position_to_cell(mouse_pos):
    """
    Muuntaa hiiren pikselisijainnin ruudukon riviksi ja sarakkeeksi.

    Tätä funktiota kutsutaan vasta sen jälkeen, kun on tarkistettu,
    että hiiren sijainti on ruudukkoalueella.
    """
    x, y = mouse_pos
    row = (y - GRID_OFFSET_Y) // CELL_SIZE
    col = (x - GRID_OFFSET_X) // CELL_SIZE
    return row, col


def is_inside_grid_area(mouse_pos):
    """Palauttaa True, jos hiiren sijainti on varsinaisella ruudukkoalueella."""
    x, y = mouse_pos
    return (
        GRID_OFFSET_X <= x < GRID_OFFSET_X + WINDOW_WIDTH
        and GRID_OFFSET_Y <= y < GRID_OFFSET_Y + WINDOW_HEIGHT
    )


def algorithm_display_name(selected_algorithm):
    """Muuntaa sisäisen algoritmiavaimen käyttäjälle näytettäväksi nimeksi."""
    names = {
        "dijkstra": "Dijkstra",
        "astar": "A*",
        "dstar_lite": "D* Lite",
    }
    return names.get(selected_algorithm, selected_algorithm or "---")


def next_click_display_name(placement_mode):
    """Kertoo käyttäjälle, mitä seuraava ruudukkoklikkaus tekee."""
    names = {
        "start": "asettaa lähtöpisteen",
        "goal": "asettaa maalin",
    }
    return names.get(placement_mode, "piirtää esteen")


# Sivupaneelit: ohjeet vasemmalla, painikkeet oikealla.
# Näin ruudukko saa koko ikkunan korkeuden käyttöönsä.
LEFT_PANEL_WIDTH = 280
RIGHT_PANEL_WIDTH = 270
SIDE_PANEL_MARGIN = 10
PANEL_HEIGHT = 0
GUIDE_HEIGHT = 0
BUTTON_WIDTH = 112
BUTTON_HEIGHT = 28
BUTTON_MARGIN = 8
QUIT_KEY = pygame.K_q

PANEL_BG = (38, 42, 48)
CARD_BG = (54, 60, 68)
ACTIVE_BUTTON_COLOR = (255, 210, 90)
PRIMARY_BUTTON_COLOR = (110, 170, 255)
QUIT_BUTTON_COLOR = (220, 95, 95)
DISABLED_BUTTON_COLOR = (120, 124, 130)
DISABLED_TEXT_COLOR = (75, 78, 82)
HELP_TEXT_COLOR = (225, 225, 225)
MUTED_TEXT_COLOR = (188, 194, 202)
AUTO_OBSTACLE_COLOR = (160, 80, 200)
AUTO_OBSTACLE_MIN = 0
AUTO_OBSTACLE_MAX = 10
AUTO_OBSTACLE_DECREASE_KEY = pygame.K_MINUS
AUTO_OBSTACLE_INCREASE_KEY = pygame.K_EQUALS

# Nämä arvot päivitetään käynnistyksessä ja ikkunan koon muuttuessa.
# Näin ruudukko skaalautuu näytölle eikä mene ikkunan ulkopuolelle.
SCREEN_WIDTH = WINDOW_WIDTH
SCREEN_HEIGHT = WINDOW_HEIGHT
GRID_OFFSET_X = 0
GRID_OFFSET_Y = 0
MIN_CELL_SIZE = 1
MAX_CELL_SIZE = 40


def update_layout_for_screen(screen_width, screen_height, grid):
    """
    Laskee ruudukolle sopivan solukoon nykyisen ikkunan koon perusteella.

    Ruudukolle varataan tila ikkunan yläosasta ja käyttöliittymäpaneeli pidetään
    näkyvissä ikkunan alaosassa. Jos ruudukko on suuri, solukokoa pienennetään
    automaattisesti niin, että koko ruudukko mahtuu näkyviin.
    """
    global SCREEN_WIDTH, SCREEN_HEIGHT, WINDOW_WIDTH, WINDOW_HEIGHT, CELL_SIZE
    global GRID_OFFSET_X, GRID_OFFSET_Y

    SCREEN_WIDTH = max(320, int(screen_width))
    SCREEN_HEIGHT = max(320, int(screen_height))

    side_panels_width = LEFT_PANEL_WIDTH + RIGHT_PANEL_WIDTH + SIDE_PANEL_MARGIN * 2
    available_grid_width = max(80, SCREEN_WIDTH - side_panels_width)
    available_grid_height = max(80, SCREEN_HEIGHT - SIDE_PANEL_MARGIN * 2)

    cell_by_width = max(1, available_grid_width // max(1, grid.cols))
    cell_by_height = max(1, available_grid_height // max(1, grid.rows))
    CELL_SIZE = max(MIN_CELL_SIZE, min(MAX_CELL_SIZE, cell_by_width, cell_by_height))

    WINDOW_WIDTH = grid.cols * CELL_SIZE
    WINDOW_HEIGHT = grid.rows * CELL_SIZE

    grid_area_x = LEFT_PANEL_WIDTH + SIDE_PANEL_MARGIN
    GRID_OFFSET_X = grid_area_x + max(0, (available_grid_width - WINDOW_WIDTH) // 2)
    GRID_OFFSET_Y = SIDE_PANEL_MARGIN + max(0, (available_grid_height - WINDOW_HEIGHT) // 2)


def recreate_layout(screen_width, screen_height, grid):
    """Päivittää mitoituksen ja luo painikkeet uuteen ikkunakokoon."""
    update_layout_for_screen(screen_width, screen_height, grid)
    return create_ui_buttons()


def create_window(screen_width, screen_height, fullscreen=False):
    """Luo ohjelmaikkunan. Oletuksena käytetään normaalia muutettavaa ikkunaa."""
    if fullscreen:
        return pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)

    return pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)


def clicked_quit_button(mouse_pos, buttons):
    """Palauttaa True, jos käyttäjä klikkasi Sulje-painiketta."""
    if buttons is None:
        return False

    for button in buttons:
        if button.label == "Sulje" and button.is_clicked(mouse_pos):
            return True

    return False


def should_quit_from_event(event, buttons=None):
    """Tarkistaa sulkemisen myös animaatioiden aikana."""
    if event.type == pygame.QUIT:
        return True

    if event.type == pygame.KEYDOWN and event.key == QUIT_KEY:
        return True

    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        return clicked_quit_button(pygame.mouse.get_pos(), buttons)

    return False


class Button:
    """Yksinkertainen Pygame-painike."""
    def __init__(self, x, y, w, h, label, key=None, color=LIGHT_GRAY, hover_color=(220, 220, 220)):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.key = key
        self.color = color
        self.hover_color = hover_color
        self.hover = False
        self.enabled = True
        self.active = False
        self.primary = False
        self.danger = False

    def draw(self, screen, font):
        if not self.enabled:
            color = DISABLED_BUTTON_COLOR
            text_color = DISABLED_TEXT_COLOR
            border_color = (80, 82, 86)
            border_width = 1
        elif self.danger:
            color = self._brighten(QUIT_BUTTON_COLOR, 18) if self.hover else QUIT_BUTTON_COLOR
            text_color = WHITE
            border_color = (120, 40, 40)
            border_width = 1
        elif self.active:
            color = self._brighten(ACTIVE_BUTTON_COLOR, 20) if self.hover else ACTIVE_BUTTON_COLOR
            text_color = BLACK
            border_color = WHITE
            border_width = 2
        elif self.primary:
            color = self._brighten(PRIMARY_BUTTON_COLOR, 18) if self.hover else PRIMARY_BUTTON_COLOR
            text_color = WHITE
            border_color = (55, 95, 150)
            border_width = 1
        else:
            color = self.hover_color if self.hover else self.color
            text_color = BLACK
            border_color = BLACK
            border_width = 1

        pygame.draw.rect(screen, color, self.rect, border_radius=6)
        pygame.draw.rect(screen, border_color, self.rect, border_width, border_radius=6)
        txt = font.render(self.label, True, text_color)
        txt_r = txt.get_rect(center=self.rect.center)
        screen.blit(txt, txt_r)

    def update_hover(self, mouse_pos):
        self.hover = self.enabled and self.rect.collidepoint(mouse_pos)

    def is_clicked(self, mouse_pos):
        return self.enabled and self.rect.collidepoint(mouse_pos)

    @staticmethod
    def _brighten(color, amount):
        return tuple(min(255, value + amount) for value in color)

def create_ui_buttons():
    """Luo painikkeet ruudukon oikealle puolelle ryhmiteltynä.

    Ryhmien otsikoita ei piirretä käyttöliittymään. Ryhmien väliin jätetään
    vain hieman enemmän pystysuuntaista tyhjää tilaa, jotta toiminnot
    hahmottuvat paremmin.
    """
    button_groups = [
        [
            ("Lähtöpiste", pygame.K_s),
            ("Maali", pygame.K_g),
        ],
        [
            ("Satunnaisesteet", pygame.K_p),
        ],
        [
            ("Dijkstra", pygame.K_d),
            ("A*", pygame.K_a),
            ("D* Lite", pygame.K_l),
        ],
        [
            ("Dynaamiset -", AUTO_OBSTACLE_DECREASE_KEY),
            ("Dynaamiset +", AUTO_OBSTACLE_INCREASE_KEY),
        ],
        [
            ("Laske reitti", pygame.K_SPACE),
            ("Aloita ajo", pygame.K_RETURN),
        ],
        [            
            ("Tyhjennä", pygame.K_c),
            ("Sulje", QUIT_KEY),
        ],
    ]

    buttons = []
    button_x = SCREEN_WIDTH - RIGHT_PANEL_WIDTH + SIDE_PANEL_MARGIN
    button_w = RIGHT_PANEL_WIDTH - SIDE_PANEL_MARGIN * 2

    group_gap = 18
    total_button_count = sum(len(group) for group in button_groups)
    total_group_gaps = group_gap * (len(button_groups) - 1)
    total_button_height = (
        total_button_count * BUTTON_HEIGHT
        + (total_button_count - 1) * BUTTON_MARGIN
        + total_group_gaps
    )

    y = max(SIDE_PANEL_MARGIN * 2 + 34, (SCREEN_HEIGHT - total_button_height) // 2)

    for group_index, group in enumerate(button_groups):
        for label, key in group:
            buttons.append(Button(button_x, y, button_w, BUTTON_HEIGHT, label, key))
            y += BUTTON_HEIGHT + BUTTON_MARGIN

        if group_index < len(button_groups) - 1:
            y += group_gap

    return buttons

def can_edit_initial_obstacles(grid, selected_algorithm):
    """Alkuperäisiä esteitä saa muokata lähtöpisteen ja maalin jälkeen ennen algoritmin valintaa."""
    return grid.start is not None and grid.goal is not None and selected_algorithm is None

def update_button_states(buttons, grid, selected_algorithm, path, last_result, auto_obstacle_count, placement_mode=None):
    """Päivittää painikkeiden tilan niin, että käyttö etenee oikeassa järjestyksessä."""
    has_start = grid.start is not None
    has_goal = grid.goal is not None
    has_start_and_goal = has_start and has_goal
    has_algorithm = selected_algorithm is not None
    can_calculate_route = has_start_and_goal and has_algorithm
    can_start_drive = bool(path) and last_result is not None and last_result.get("success", False)

    for button in buttons:
        button.enabled = True
        button.active = False
        button.primary = False
        button.danger = button.key == QUIT_KEY

        if button.key == pygame.K_s:
            button.enabled = not has_start or placement_mode == "start"
        elif button.key == pygame.K_g:
            button.enabled = has_start and (not has_goal or placement_mode == "goal")
        elif button.key == pygame.K_p:
            button.enabled = can_edit_initial_obstacles(grid, selected_algorithm)
        elif button.key in (pygame.K_d, pygame.K_a, pygame.K_l):
            button.enabled = has_start_and_goal
        elif button.key == AUTO_OBSTACLE_DECREASE_KEY:
            button.enabled = has_algorithm and auto_obstacle_count > AUTO_OBSTACLE_MIN
        elif button.key == AUTO_OBSTACLE_INCREASE_KEY:
            button.enabled = has_algorithm and auto_obstacle_count < AUTO_OBSTACLE_MAX
        elif button.key == pygame.K_SPACE:
            button.enabled = can_calculate_route
        elif button.key == pygame.K_RETURN:
            button.enabled = can_start_drive

        if button.key == pygame.K_s and placement_mode == "start":
            button.active = True
        elif button.key == pygame.K_g and placement_mode == "goal":
            button.active = True
        elif button.key == pygame.K_d and selected_algorithm == "dijkstra":
            button.active = True
        elif button.key == pygame.K_a and selected_algorithm == "astar":
            button.active = True
        elif button.key == pygame.K_l and selected_algorithm == "dstar_lite":
            button.active = True

def get_next_recommended_key(grid, selected_algorithm, path, last_result, placement_mode=None):
    """Palauttaa seuraavan loogisen päävaiheen painikkeen."""
    if placement_mode in ("start", "goal"):
        return None
    if grid.start is None:
        return pygame.K_s
    if grid.goal is None:
        return pygame.K_g
    if selected_algorithm is None:
        return pygame.K_d
    if not path or last_result is None:
        return pygame.K_SPACE
    if last_result.get("success", False):
        return pygame.K_RETURN
    return pygame.K_SPACE

def get_status_lines(grid, selected_algorithm, path, auto_obstacle_count):
    """Muodostaa vasemman sivupaneelin pysyvät käyttöohjeet."""
    instructions = [
        "1) Valitse lähtöpiste.",
        "2) Valitse maali.",
        "3) Piirrä esteet hiirellä, tai",
        " lisää satunnaisesteet.",
        "4) Valitse algoritmi.",
        "5) Laske reitti.",
        "6) Aloita ajo.",
        "",
        "Esteet:",
        "Maalaa vasemmalla hiirellä ",
        "lisätäksesi.",
        "Maalaa oikealla hiirellä ",
        "poistaaksesi.",
        "",
        "Ajon aikana:",
        "Klikkaa reitin eteen uusi este ",
        "manuaalisesti TAI",
        "Dyn +/- lisää automaattisia",
        " ajonaikaisia esteitä (parempi).",
        "",
        "Sulje lopettaa ohjelman.",
    ]

    start_text = str(grid.start) if grid.start is not None else "-"
    goal_text = str(grid.goal) if grid.goal is not None else "-"
    algorithm_text = algorithm_display_name(selected_algorithm)
    path_text = f"{max(0, len(path) - 1)} askelta" if path else "-"

    status = [
        "Tila",
        f"Lähtö: {start_text}",
        f"Maali: {goal_text}",
        f"Algoritmi: {algorithm_text}",
        f"Reitti: {path_text}",
        f"Dynaamiset esteet: {auto_obstacle_count}",
    ]
    return instructions, status

def draw_grid(screen, grid, path=None, visited=None, vehicle_position=None, buttons=None, font=None, selected_algorithm=None, placement_mode=None, auto_obstacle_count=0, auto_obstacle_positions=None):
    """ 
    Piirtää ruudukon, esteet, lähtöpisteen, kohdepisteen,
    algoritmin tutkimat ruudut, löydetyn reitin ja ajoneuvon.
    """
    if path is None:
        path = []

    if visited is None:
        visited = []

    if auto_obstacle_positions is None:
        auto_obstacle_positions = set()

    screen.fill(WHITE)

    path_set = set(path)
    visited_set = set(visited)

    for row in range(grid.rows):
        for col in range(grid.cols):
            position = (row, col)

            rect = pygame.Rect(
                GRID_OFFSET_X + col * CELL_SIZE,
                GRID_OFFSET_Y + row * CELL_SIZE,
                CELL_SIZE,
                CELL_SIZE
            )

            if position == vehicle_position:
                pygame.draw.rect(screen, ORANGE, rect)
            elif position == grid.start:
                pygame.draw.rect(screen, GREEN, rect)
            elif position == grid.goal:
                pygame.draw.rect(screen, RED, rect)
            elif position in auto_obstacle_positions:
                pygame.draw.rect(screen, AUTO_OBSTACLE_COLOR, rect)
            elif grid.is_obstacle(row, col):
                pygame.draw.rect(screen, BLACK, rect)
            elif position in path_set:
                pygame.draw.rect(screen, BLUE, rect)
            elif position in visited_set:
                pygame.draw.rect(screen, YELLOW, rect)
            else:
                pygame.draw.rect(screen, WHITE, rect)

            pygame.draw.rect(screen, LIGHT_GRAY, rect, 1)

    # Piirretään sivupaneelit, jos nappipaneeli annettu.
    if buttons is not None and font is not None:
        left_rect = pygame.Rect(
            SIDE_PANEL_MARGIN,
            SIDE_PANEL_MARGIN,
            LEFT_PANEL_WIDTH - SIDE_PANEL_MARGIN * 2,
            SCREEN_HEIGHT - SIDE_PANEL_MARGIN * 2,
        )
        right_rect = pygame.Rect(
            SCREEN_WIDTH - RIGHT_PANEL_WIDTH + SIDE_PANEL_MARGIN,
            SIDE_PANEL_MARGIN,
            RIGHT_PANEL_WIDTH - SIDE_PANEL_MARGIN * 2,
            SCREEN_HEIGHT - SIDE_PANEL_MARGIN * 2,
        )

        pygame.draw.rect(screen, PANEL_BG, pygame.Rect(0, 0, LEFT_PANEL_WIDTH, SCREEN_HEIGHT))
        pygame.draw.rect(screen, PANEL_BG, pygame.Rect(SCREEN_WIDTH - RIGHT_PANEL_WIDTH, 0, RIGHT_PANEL_WIDTH, SCREEN_HEIGHT))

        pygame.draw.rect(screen, CARD_BG, left_rect, border_radius=8)
        pygame.draw.rect(screen, (78, 86, 96), left_rect, 1, border_radius=8)

        pygame.draw.rect(screen, (44, 49, 56), right_rect, border_radius=8)
        pygame.draw.rect(screen, (70, 78, 88), right_rect, 1, border_radius=8)

        instructions, status = get_status_lines(
            grid,
            selected_algorithm,
            path,
            auto_obstacle_count,
        )

        title_surf = font.render("Ohjeet", True, WHITE)
        screen.blit(title_surf, (left_rect.x + 12, left_rect.y + 12))

        text_x = left_rect.x + 12
        text_y = left_rect.y + 40
        line_gap = 18

        for line in instructions:
            if line == "":
                text_y += line_gap // 2
                continue

            color = HELP_TEXT_COLOR
            if line in ("Esteet:", "Ajon aikana:"):
                color = WHITE

            line_surf = font.render(line, True, color)
            screen.blit(line_surf, (text_x, text_y))
            text_y += line_gap

        status_y = max(text_y + 12, left_rect.bottom - 128)
        status_title = font.render(status[0], True, WHITE)
        screen.blit(status_title, (text_x, status_y))

        for index, line in enumerate(status[1:]):
            line_surf = font.render(line, True, MUTED_TEXT_COLOR)
            screen.blit(line_surf, (text_x, status_y + 24 + index * line_gap))

        button_title = font.render("Toiminnot", True, WHITE)
        screen.blit(button_title, (right_rect.x + 12, right_rect.y + 12))

        for b in buttons:
            b.draw(screen, font)

def animate_search(screen, grid, visited_order, path, vehicle_position=None, buttons=None, font=None, selected_algorithm=None, placement_mode=None, auto_obstacle_count=0, auto_obstacle_positions=None):
    """
    Näyttää algoritmin etenemisen vaiheittain.

    Varsinainen laskenta on tehty ennen tätä, joten animaation viive
    ei vaikuta mitattuun laskenta-aikaan.
    """
    if auto_obstacle_positions is None:
        auto_obstacle_positions = set()

    shown_visited = []
    visited_step = get_animation_step(len(visited_order))

    for index, cell in enumerate(visited_order):
        shown_visited.append(cell)
        is_last_cell = index == len(visited_order) - 1

        if index % visited_step != 0 and not is_last_cell:
            continue

        draw_grid(
            screen,
            grid,
            path=[],
            visited=shown_visited,
            vehicle_position=vehicle_position,
            buttons=buttons,
            font=font,
            selected_algorithm=selected_algorithm,
            placement_mode=placement_mode,
            auto_obstacle_count=auto_obstacle_count,
            auto_obstacle_positions=auto_obstacle_positions,
        )
        pygame.display.flip()
        pygame.time.delay(VISITED_ANIMATION_DELAY_MS)

        for event in pygame.event.get():
            if should_quit_from_event(event, buttons):
                pygame.quit()
                sys.exit()

    shown_path = []

    for cell in path:
        shown_path.append(cell)

        draw_grid(
            screen,
            grid,
            path=shown_path,
            visited=visited_order,
            vehicle_position=vehicle_position,
            buttons=buttons,
            font=font,
            selected_algorithm=selected_algorithm,
            placement_mode=placement_mode,
            auto_obstacle_count=auto_obstacle_count,
            auto_obstacle_positions=auto_obstacle_positions,
        )
        pygame.display.flip()
        pygame.time.delay(PATH_ANIMATION_DELAY_MS)

        for event in pygame.event.get():
            if should_quit_from_event(event, buttons):
                pygame.quit()
                sys.exit()


def run_selected_algorithm(grid, selected_algorithm, start, goal):
    """
    Suorittaa käyttäjän valitseman algoritmin annetusta lähtöruudusta kohderuutuun.
    """
    if selected_algorithm == "dijkstra":
        return dijkstra(grid, start, goal)

    if selected_algorithm == "astar":
        return astar(grid, start, goal)

    if selected_algorithm == "dstar_lite":
        return dstar_lite_search(grid, start, goal)

    raise ValueError(f"Tuntematon algoritmi: {selected_algorithm}")

def print_result(result, prefix=None):
    """
    Tulostaa algoritmin tulokset terminaaliin.
    """
    title = result["algorithm"]

    if prefix is not None:
        title = f"{prefix}: {title}"

    print(f"\n{title}")
    print(f"Onnistui: {result['success']}")
    print(f"Reitin pituus: {result['path_length']} askelta")
    print(f"Tutkitut ruudut: {result['visited_count']}")
    print(f"Laskenta-aika: {result['calculation_time']:.8f} sekuntia")


def get_animation_step(total_items):
    """Nopeuttaa hakuvaiheen visualisointia, kun tutkittuja ruutuja on paljon."""
    if total_items <= 200:
        return 1
    if total_items <= 500:
        return 3
    if total_items <= 1000:
        return 5
    if total_items <= 3000:
        return 10
    return 20


def get_vehicle_delay(path_length):
    """Nopeuttaa ajoneuvon etenemisanimaatiota pitkillä reiteillä."""
    if path_length <= 50:
        return VEHICLE_MOVE_DELAY_MS
    if path_length <= 100:
        return max(20, VEHICLE_MOVE_DELAY_MS // 2)
    if path_length <= 200:
        return max(10, VEHICLE_MOVE_DELAY_MS // 4)
    return max(5, VEHICLE_MOVE_DELAY_MS // 8)


def get_auto_obstacle_trigger_fractions(auto_obstacle_count):
    """
    Palauttaa etenemiskohdat, joissa automaattiset esteet yritetään lisätä.

    Arvot jaetaan toimituksen alku- ja loppuosan väliin, jotta esteitä ei
    lisätä heti alussa tai aivan maaliruudun vieressä.
    """
    count = max(AUTO_OBSTACLE_MIN, min(AUTO_OBSTACLE_MAX, auto_obstacle_count))

    if count == 0:
        return []

    if count == 1:
        return [0.35]

    start_fraction = 0.20
    end_fraction = 0.80
    step = (end_fraction - start_fraction) / (count - 1)

    return [start_fraction + step * index for index in range(count)]


def find_future_obstacle_on_path(grid, current_path, current_index, vehicle_position):
    """
    Etsii nykyiseltä reitiltä ajoneuvon edestä ruudun, johon voidaan lisätä este.
    Maalia, lähtöä tai ajoneuvon nykyistä sijaintia ei käytetä esteenä.
    """
    if len(current_path) < 4:
        return None

    lookahead = max(2, len(current_path) // 10)
    preferred_index = min(len(current_path) - 2, current_index + lookahead)

    candidate_indexes = list(range(preferred_index, len(current_path) - 1))
    candidate_indexes += list(range(current_index + 1, preferred_index))

    for index in candidate_indexes:
        if index <= current_index or index >= len(current_path) - 1:
            continue

        position = current_path[index]
        row, col = position

        if position in (vehicle_position, grid.start, grid.goal):
            continue
        if grid.is_obstacle(row, col):
            continue

        return position

    return None


def should_add_automatic_obstacle(current_index, current_path_length, auto_obstacle_count, auto_obstacles_added):
    """Päättelee, onko seuraavan automaattisen esteen lisäämisen aika."""
    trigger_fractions = get_auto_obstacle_trigger_fractions(auto_obstacle_count)

    if auto_obstacles_added >= len(trigger_fractions):
        return False
    if current_path_length <= 1:
        return False

    progress = current_index / max(1, current_path_length - 1)
    return progress >= trigger_fractions[auto_obstacles_added]


def add_automatic_obstacle_if_needed(
    grid,
    current_path,
    current_index,
    vehicle_position,
    auto_obstacle_count,
    auto_obstacles_added,
):
    """
    Lisää automaattisen dynaamisen esteen nykyisen reitin loppuosalle,
    jos valittu etenemiskohta on saavutettu.
    """
    if not should_add_automatic_obstacle(
        current_index,
        len(current_path),
        auto_obstacle_count,
        auto_obstacles_added,
    ):
        return None

    obstacle_position = find_future_obstacle_on_path(
        grid,
        current_path,
        current_index,
        vehicle_position,
    )

    if obstacle_position is None:
        return None

    row, col = obstacle_position
    grid.add_obstacle(row, col)
    print(f"\nAutomaattinen dynaaminen este lisättiin ruutuun: {obstacle_position}")
    return obstacle_position


def handle_dynamic_click(grid, vehicle_position, mouse_pos):
    """
    Käsittelee ajon aikana tehdyn klikkauksen.

    Klikattu ruutu muuttuu esteeksi, jos se ei ole:
    - ajoneuvon nykyinen sijainti
    - lähtöpiste
    - kohdepiste

    Palauttaa lisätyn esteen sijainnin tai None.
    """
    if not is_inside_grid_area(mouse_pos):
        return None

    row, col = mouse_position_to_cell(mouse_pos)
    obstacle_position = (row, col)

    if not (0 <= row < grid.rows and 0 <= col < grid.cols):
        return None

    if obstacle_position == vehicle_position:
        print("Et voi lisätä estettä ajoneuvon nykyiseen sijaintiin.")
        return None

    if obstacle_position == grid.start or obstacle_position == grid.goal:
        print("Et voi lisätä estettä lähtö- tai kohdepisteeseen.")
        return None

    grid.add_obstacle(row, col)
    print(f"\nManuaalinen dynaaminen este lisättiin ruutuun: {obstacle_position}")

    return obstacle_position


def animate_vehicle_with_manual_obstacles(
    screen,
    grid,
    initial_path,
    initial_visited,
    selected_algorithm,
    initial_result,
    buttons=None,
    font=None,
    auto_obstacle_count=0
):
    """
    Liikuttaa ajoneuvoa reittiä pitkin.

    Ajon aikana käyttäjä voi lisätä esteen hiiren vasemmalla klikkauksella.
    Jos este osuu jäljellä olevalle reitille, algoritmi laskee uuden reitin
    ajoneuvon nykyisestä sijainnista kohdepisteeseen.
    """
    metrics = SimulationMetrics(initial_result["algorithm"])
    metrics.set_scenario_info(grid)
    metrics.set_initial_result(initial_result)

    # Tallennetaan alkuperäiset esteet, jotta manuaaliset dynaamiset esteet
    # eivät jää seuraavaan ajoon.
    base_obstacles = set(grid.obstacles)
    auto_obstacle_positions = set()

    if not initial_path:
        print("Reittiä ei ole, joten ajoneuvo ei voi liikkua.")
        metrics.set_success(False)
        metrics.print_summary()
        metrics.save_to_csv("results.csv")
        print("Tulokset tallennettu tiedostoon results.csv")
        grid.obstacles = set(base_obstacles)
        return [], [], None, auto_obstacle_positions

    current_path = initial_path
    current_visited = initial_visited
    vehicle_position = current_path[0]

    travelled_path = []
    current_index = 0
    auto_obstacles_added = 0

    while current_index < len(current_path):
        vehicle_position = current_path[current_index]
        travelled_path.append(vehicle_position)

        draw_grid(
            screen,
            grid,
            path=current_path,
            visited=current_visited,
            vehicle_position=vehicle_position,
            buttons=buttons,
            font=font,
            selected_algorithm=selected_algorithm,
            placement_mode=None,
            auto_obstacle_count=auto_obstacle_count,
            auto_obstacle_positions=auto_obstacle_positions,
        )
        pygame.display.flip()

        automatic_obstacle_position = add_automatic_obstacle_if_needed(
            grid,
            current_path,
            current_index,
            vehicle_position,
            auto_obstacle_count,
            auto_obstacles_added,
        )

        if automatic_obstacle_position is not None:
            auto_obstacles_added += 1
            auto_obstacle_positions.add(automatic_obstacle_position)
            metrics.set_dynamic_obstacle(automatic_obstacle_position)
            print("Automaattinen este vaikuttaa jäljellä olevaan reittiin. Lasketaan uusi reitti.")
            metrics.add_effective_obstacle(automatic_obstacle_position)

            reroute_result = run_selected_algorithm(
                grid,
                selected_algorithm,
                vehicle_position,
                grid.goal
            )

            metrics.add_reroute_result(reroute_result)
            print_result(reroute_result, prefix="Uudelleenreititys")

            if not reroute_result["success"]:
                print("Uutta reittiä ei löytynyt. Simulaatio keskeytyy.")
                metrics.set_travelled_path(travelled_path)
                metrics.set_success(False)
                metrics.print_summary()
                metrics.save_to_csv("results.csv")
                print("Tulokset tallennettu tiedostoon results.csv")
                grid.obstacles = set(base_obstacles)
                return travelled_path, current_visited, vehicle_position, auto_obstacle_positions

            current_path = reroute_result["path"]
            current_visited = reroute_result["visited_order"]

            animate_search(
                screen,
                grid,
                current_visited,
                current_path,
                vehicle_position=vehicle_position,
                buttons=buttons,
                font=font,
                selected_algorithm=selected_algorithm,
                placement_mode=None,
                auto_obstacle_count=auto_obstacle_count,
                auto_obstacle_positions=auto_obstacle_positions,
            )

            current_index = 0
            continue

        start_tick = pygame.time.get_ticks()
        rerouted = False
        vehicle_delay = get_vehicle_delay(len(current_path))

        while pygame.time.get_ticks() - start_tick < vehicle_delay:
            for event in pygame.event.get():
                if should_quit_from_event(event, buttons):
                    pygame.quit()
                    sys.exit()

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_pos = pygame.mouse.get_pos()

                    if not is_inside_grid_area(mouse_pos):
                        continue

                    obstacle_position = handle_dynamic_click(
                        grid,
                        vehicle_position,
                        mouse_pos
                    )

                    if obstacle_position is None:
                        continue

                    metrics.set_dynamic_obstacle(obstacle_position)

                    remaining_path = current_path[current_index + 1:]

                    if obstacle_position in remaining_path:
                        print("Este vaikuttaa jäljellä olevaan reittiin. Lasketaan uusi reitti.")
                        metrics.add_effective_obstacle(obstacle_position)

                        reroute_result = run_selected_algorithm(
                            grid,
                            selected_algorithm,
                            vehicle_position,
                            grid.goal
                        )

                        metrics.add_reroute_result(reroute_result)
                        print_result(reroute_result, prefix="Uudelleenreititys")

                        if not reroute_result["success"]:
                            print("Uutta reittiä ei löytynyt. Simulaatio keskeytyy.")
                            metrics.set_travelled_path(travelled_path)
                            metrics.set_success(False)
                            metrics.print_summary()
                            metrics.save_to_csv("results.csv")
                            print("Tulokset tallennettu tiedostoon results.csv")
                            grid.obstacles = set(base_obstacles)
                            return travelled_path, current_visited, vehicle_position, auto_obstacle_positions

                        current_path = reroute_result["path"]
                        current_visited = reroute_result["visited_order"]

                        animate_search(
                            screen,
                            grid,
                            current_visited,
                            current_path,
                            vehicle_position=vehicle_position,
                            buttons=buttons,
                            font=font,
                            selected_algorithm=selected_algorithm,
                            placement_mode=None,
                            auto_obstacle_count=auto_obstacle_count,
                            auto_obstacle_positions=auto_obstacle_positions,
                        )

                        # Uusi reitti alkaa ajoneuvon nykyisestä sijainnista.
                        current_index = 0
                        rerouted = True
                        break

                    else:
                        print("Este ei vaikuta jäljellä olevaan reittiin. Ajoneuvo jatkaa samaa reittiä.")

            if rerouted:
                break

        if rerouted:
            continue

        current_index += 1

    print("\nAjoneuvo saavutti kohdepisteen.")

    metrics.set_travelled_path(travelled_path)
    metrics.set_success(True)
    metrics.print_summary()
    metrics.save_to_csv("results.csv")
    print("Tulokset tallennettu tiedostoon results.csv")

    # Palautetaan alkuperäiset esteet, jotta seuraava ajo alkaa samasta lähtötilanteesta.
    grid.obstacles = set(base_obstacles)

    return current_path, current_visited, vehicle_position, auto_obstacle_positions

def animate_vehicle_with_dstar_lite(
    screen,
    grid,
    initial_path,
    initial_visited,
    initial_result,
    buttons=None,
    font=None,
    auto_obstacle_count=0
):
    """
    Liikuttaa ajoneuvoa D* Lite -reitillä inkrementaalisesti.

    Tässä versiossa D* Lite -planner säilytetään koko ajon ajan.
    Kun ajoneuvo liikkuu, plannerin lähtöpiste päivitetään.
    Kun käyttäjä lisää esteen ajon aikana, planner päivittää aiemmat
    g- ja rhs-arvot eikä aloita koko hakua alusta.
    """
    metrics = SimulationMetrics(initial_result["algorithm"])
    metrics.set_scenario_info(grid)
    metrics.set_initial_result(initial_result)

    base_obstacles = set(grid.obstacles)
    auto_obstacle_positions = set()

    if not initial_path:
        print("Reittiä ei ole, joten ajoneuvo ei voi liikkua.")
        metrics.set_success(False)
        metrics.print_summary()
        metrics.save_to_csv("results.csv")
        print("Tulokset tallennettu tiedostoon results.csv")
        grid.obstacles = set(base_obstacles)
        return [], [], None, auto_obstacle_positions

    # Luodaan D* Lite -planner kerran koko ajon ajaksi.
    planner = DStarLite(grid, grid.start, grid.goal)
    planner.compute_shortest_path(reset_visited=True)

    current_path = planner.get_path()
    current_visited = list(planner.visited_order)

    vehicle_position = current_path[0]
    travelled_path = []
    current_index = 0
    auto_obstacles_added = 0

    while current_index < len(current_path):
        vehicle_position = current_path[current_index]
        travelled_path.append(vehicle_position)

        # Päivitetään D* Liten nykyinen lähtöpiste ajoneuvon sijaintiin.
        planner.move_start(vehicle_position)

        draw_grid(
            screen,
            grid,
            path=current_path,
            visited=current_visited,
            vehicle_position=vehicle_position,
            buttons=buttons,
            font=font,
            selected_algorithm=initial_result.get("algorithm", "D* Lite"),
            placement_mode=None,
            auto_obstacle_count=auto_obstacle_count,
            auto_obstacle_positions=auto_obstacle_positions,
        )
        pygame.display.flip()

        automatic_obstacle_position = add_automatic_obstacle_if_needed(
            grid,
            current_path,
            current_index,
            vehicle_position,
            auto_obstacle_count,
            auto_obstacles_added,
        )

        if automatic_obstacle_position is not None:
            auto_obstacles_added += 1
            auto_obstacle_positions.add(automatic_obstacle_position)
            metrics.set_dynamic_obstacle(automatic_obstacle_position)
            print(
                "Automaattinen este vaikuttaa jäljellä olevaan reittiin. "
                "Päivitetään D* Lite -planneria inkrementaalisesti."
            )
            metrics.add_effective_obstacle(automatic_obstacle_position)

            replanning_start_time = time.perf_counter()
            planner.update_obstacle(automatic_obstacle_position)
            planner.compute_shortest_path(reset_visited=True)
            replanning_end_time = time.perf_counter()
            replanning_time = replanning_end_time - replanning_start_time

            new_path = planner.get_path()
            new_visited = list(planner.visited_order)

            reroute_result = {
                "algorithm": "D* Lite",
                "path": new_path,
                "visited_order": new_visited,
                "calculation_time": replanning_time,
                "visited_count": len(new_visited),
                "path_length": max(0, len(new_path) - 1),
                "success": len(new_path) > 0,
            }

            metrics.add_reroute_result(reroute_result)
            print_result(reroute_result, prefix="Uudelleenreititys")

            if not reroute_result["success"]:
                print("Uutta reittiä ei löytynyt. Simulaatio keskeytyy.")
                metrics.set_travelled_path(travelled_path)
                metrics.set_success(False)
                metrics.print_summary()
                metrics.save_to_csv("results.csv")
                print("Tulokset tallennettu tiedostoon results.csv")
                grid.obstacles = set(base_obstacles)
                return travelled_path, current_visited, vehicle_position, auto_obstacle_positions

            current_path = new_path
            current_visited = new_visited

            animate_search(
                screen,
                grid,
                current_visited,
                current_path,
                vehicle_position=vehicle_position,
                buttons=buttons,
                font=font,
                selected_algorithm=initial_result.get("algorithm", "D* Lite"),
                placement_mode=None,
                auto_obstacle_count=auto_obstacle_count,
                auto_obstacle_positions=auto_obstacle_positions,
            )

            current_index = 0
            continue

        start_tick = pygame.time.get_ticks()
        rerouted = False
        vehicle_delay = get_vehicle_delay(len(current_path))

        while pygame.time.get_ticks() - start_tick < vehicle_delay:
            for event in pygame.event.get():
                if should_quit_from_event(event, buttons):
                    pygame.quit()
                    sys.exit()

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_pos = pygame.mouse.get_pos()

                    if not is_inside_grid_area(mouse_pos):
                        continue

                    obstacle_position = handle_dynamic_click(
                        grid,
                        vehicle_position,
                        mouse_pos
                    )

                    if obstacle_position is None:
                        continue

                    metrics.set_dynamic_obstacle(obstacle_position)

                    remaining_path = current_path[current_index + 1:]

                    if obstacle_position in remaining_path:
                        print(
                            "Este vaikuttaa jäljellä olevaan reittiin. "
                            "Päivitetään D* Lite -planneria inkrementaalisesti."
                        )
                        metrics.add_effective_obstacle(obstacle_position)

                        replanning_start_time = time.perf_counter()

                        # Este on jo lisätty grid.obstacles-joukkoon.
                        # Nyt D* Lite päivittää aiempaa tilaansa.
                        planner.update_obstacle(obstacle_position)
                        planner.compute_shortest_path(reset_visited=True)

                        replanning_end_time = time.perf_counter()
                        replanning_time = replanning_end_time - replanning_start_time

                        new_path = planner.get_path()
                        new_visited = list(planner.visited_order)

                        reroute_result = {
                            "algorithm": "D* Lite",
                            "path": new_path,
                            "visited_order": new_visited,
                            "calculation_time": replanning_time,
                            "visited_count": len(new_visited),
                            "path_length": max(0, len(new_path) - 1),
                            "success": len(new_path) > 0,
                        }

                        metrics.add_reroute_result(reroute_result)
                        print_result(reroute_result, prefix="Uudelleenreititys")

                        if not reroute_result["success"]:
                            print("Uutta reittiä ei löytynyt. Simulaatio keskeytyy.")
                            metrics.set_travelled_path(travelled_path)
                            metrics.set_success(False)
                            metrics.print_summary()
                            metrics.save_to_csv("results.csv")
                            print("Tulokset tallennettu tiedostoon results.csv")
                            grid.obstacles = set(base_obstacles)
                            return travelled_path, current_visited, vehicle_position, auto_obstacle_positions

                        current_path = new_path
                        current_visited = new_visited

                        animate_search(
                            screen,
                            grid,
                            current_visited,
                            current_path,
                            vehicle_position=vehicle_position,
                            buttons=buttons,
                            font=font,
                            selected_algorithm=initial_result.get("algorithm", "D* Lite"),
                            placement_mode=None,
                            auto_obstacle_count=auto_obstacle_count,
                            auto_obstacle_positions=auto_obstacle_positions,
                        )

                        # Uusi reitti alkaa ajoneuvon nykyisestä sijainnista.
                        current_index = 0
                        rerouted = True
                        break

                    else:
                        print("Este ei vaikuta jäljellä olevaan reittiin. Ajoneuvo jatkaa samaa reittiä.")

            if rerouted:
                break

        if rerouted:
            continue

        current_index += 1

    print("\nAjoneuvo saavutti kohdepisteen.")

    metrics.set_travelled_path(travelled_path)
    metrics.set_success(True)
    metrics.print_summary()
    metrics.save_to_csv("results.csv")
    print("Tulokset tallennettu tiedostoon results.csv")

    grid.obstacles = set(base_obstacles)

    return current_path, current_visited, vehicle_position, auto_obstacle_positions

def main():
    pygame.init()

    clock = pygame.time.Clock()
    grid = Grid()

    display_info = pygame.display.Info()
    screen_width = min(max(1100, display_info.current_w - 120), display_info.current_w)
    screen_height = min(max(620, display_info.current_h - 220), display_info.current_h)

    update_layout_for_screen(screen_width, screen_height, grid)

    # Oletuksena käytetään normaalia muutettavaa ikkunaa.
    # Ohjeet ovat vasemmalla ja painikkeet oikealla, joten fullscreeniä ei tarvita.
    fullscreen = False
    screen = create_window(SCREEN_WIDTH, SCREEN_HEIGHT, fullscreen=False)
    pygame.display.set_caption("Ruudukkopohjainen reitinhakusimulaatio")

    # UI-fontti ja napit
    font = pygame.font.Font(None, 20)
    buttons = create_ui_buttons()

    selected_algorithm = None
    auto_obstacle_count = 0
    visible_auto_obstacle_positions = set()

    path = []
    visited = []
    vehicle_position = None
    last_result = None

    drawing_obstacles = False
    erasing_obstacles = False
    last_drawn_cell = None

    # Uusi, luotettavampi asetuslogiikka:
    # S painetaan kerran -> seuraava klikkaus asettaa lähtöpisteen.
    # G painetaan kerran -> seuraava klikkaus asettaa kohdepisteen.
    placement_mode = None

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.VIDEORESIZE and not fullscreen:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                buttons = recreate_layout(event.w, event.h, grid)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()

                # Jos klikataan painiketta, käsitellään se ensin.
                clicked_button = False
                for b in buttons:
                    if b.is_clicked(mouse_pos):
                        ev = pygame.event.Event(pygame.KEYDOWN, key=b.key)
                        pygame.event.post(ev)
                        clicked_button = True
                        break

                if clicked_button:
                    continue

                if not is_inside_grid_area(mouse_pos):
                    continue

                row, col = mouse_position_to_cell(mouse_pos)

                if placement_mode == "start":
                    grid.set_start(row, col)
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None
                    selected_algorithm = None
                    visible_auto_obstacle_positions.clear()

                    print(f"Lähtöpiste asetettu: {(row, col)}")

                elif placement_mode == "goal":
                    grid.set_goal(row, col)
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None
                    selected_algorithm = None
                    visible_auto_obstacle_positions.clear()

                    print(f"Kohdepiste asetettu: {(row, col)}")

                elif event.button == 1 and can_edit_initial_obstacles(grid, selected_algorithm):
                    drawing_obstacles = True
                    erasing_obstacles = False
                    last_drawn_cell = (row, col)

                    grid.add_obstacle(row, col)

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None

                elif event.button == 3 and can_edit_initial_obstacles(grid, selected_algorithm):
                    erasing_obstacles = True
                    drawing_obstacles = False
                    last_drawn_cell = (row, col)

                    grid.remove_obstacle(row, col)

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None

            elif event.type == pygame.MOUSEBUTTONUP:
                drawing_obstacles = False
                erasing_obstacles = False
                last_drawn_cell = None

            elif event.type == pygame.MOUSEMOTION:
                # Päivitetään nappien hover-tila
                for b in buttons:
                    b.update_hover(pygame.mouse.get_pos())

                if drawing_obstacles or erasing_obstacles:
                    mouse_pos = pygame.mouse.get_pos()

                    if not is_inside_grid_area(mouse_pos):
                        continue

                    row, col = mouse_position_to_cell(mouse_pos)
                    current_cell = (row, col)

                    if current_cell != last_drawn_cell:
                        if drawing_obstacles:
                            grid.add_obstacle(row, col)
                        elif erasing_obstacles:
                            grid.remove_obstacle(row, col)

                        last_drawn_cell = current_cell

                        path = []
                        visited = []
                        vehicle_position = None
                        last_result = None
    
            elif event.type == pygame.KEYDOWN:
                if event.key == QUIT_KEY:
                    running = False

                elif event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    if fullscreen:
                        display_info = pygame.display.Info()
                        screen_width = display_info.current_w
                        screen_height = display_info.current_h
                        update_layout_for_screen(screen_width, screen_height, grid)
                        screen = create_window(SCREEN_WIDTH, SCREEN_HEIGHT, fullscreen=True)
                    else:
                        windowed_width = min(1280, SCREEN_WIDTH)
                        windowed_height = min(900, SCREEN_HEIGHT)
                        update_layout_for_screen(windowed_width, windowed_height, grid)
                        screen = create_window(SCREEN_WIDTH, SCREEN_HEIGHT, fullscreen=False)
                    buttons = create_ui_buttons()

                elif event.key == pygame.K_ESCAPE and fullscreen:
                    fullscreen = False
                    windowed_width = min(1280, SCREEN_WIDTH)
                    windowed_height = min(900, SCREEN_HEIGHT)
                    update_layout_for_screen(windowed_width, windowed_height, grid)
                    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
                    buttons = create_ui_buttons()

                elif event.key == AUTO_OBSTACLE_DECREASE_KEY:
                    if selected_algorithm is None:
                        print("\nValitse ensin algoritmi ennen ajonaikaisten esteiden määrää.")
                    else:
                        auto_obstacle_count = max(AUTO_OBSTACLE_MIN, auto_obstacle_count - 1)
                        print(f"\nAutomaattisia ajonaikaisia esteitä: {auto_obstacle_count}")

                elif event.key == AUTO_OBSTACLE_INCREASE_KEY:
                    if selected_algorithm is None:
                        print("\nValitse ensin algoritmi ennen ajonaikaisten esteiden määrää.")
                    else:
                        auto_obstacle_count = min(AUTO_OBSTACLE_MAX, auto_obstacle_count + 1)
                        print(f"\nAutomaattisia ajonaikaisia esteitä: {auto_obstacle_count}")

                elif event.key == pygame.K_s:
                    if grid.start is not None:
                        print("\nLähtöpiste on jo asetettu. Tyhjennä ruudukko, jos haluat aloittaa alusta.")
                        continue
                    placement_mode = "start"
                    drawing_obstacles = False
                    erasing_obstacles = False
                    last_drawn_cell = None
                    print("\nLähtöpisteen asetus valittu. Klikkaa ruutua.")

                elif event.key == pygame.K_g:
                    if grid.start is None:
                        print("\nValitse ensin lähtöpiste.")
                        continue
                    if grid.goal is not None:
                        print("\nMaali on jo asetettu. Tyhjennä ruudukko, jos haluat aloittaa alusta.")
                        continue
                    placement_mode = "goal"
                    drawing_obstacles = False
                    erasing_obstacles = False
                    last_drawn_cell = None
                    print("\nKohdepisteen asetus valittu. Klikkaa ruutua.")

                elif event.key == pygame.K_d:
                    if grid.start is None or grid.goal is None:
                        print("\nValitse ensin lähtöpiste ja maali.")
                        continue
                    selected_algorithm = "dijkstra"
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None
                    visible_auto_obstacle_positions.clear()
                    print("\nValittu algoritmi: Dijkstra")

                elif event.key == pygame.K_a:
                    if grid.start is None or grid.goal is None:
                        print("\nValitse ensin lähtöpiste ja maali.")
                        continue
                    selected_algorithm = "astar"
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None
                    visible_auto_obstacle_positions.clear()
                    print("\nValittu algoritmi: A*")

                elif event.key == pygame.K_l:
                    if grid.start is None or grid.goal is None:
                        print("\nValitse ensin lähtöpiste ja maali.")
                        continue
                    selected_algorithm = "dstar_lite"
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None
                    visible_auto_obstacle_positions.clear()
                    print("\nValittu algoritmi: D* Lite")

                elif event.key == pygame.K_c:
                    grid.clear()
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None
                    selected_algorithm = None
                    auto_obstacle_count = 0
                    visible_auto_obstacle_positions.clear()
                    print("\nRuudukko tyhjennetty.")

                elif event.key == pygame.K_p:
                    if not can_edit_initial_obstacles(grid, selected_algorithm):
                        print("\nSatunnaisesteet voi lisätä vasta lähtöpisteen ja maalin jälkeen, ennen algoritmin valintaa.")
                        continue
                    grid.generate_random_obstacles()
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None

                    print("\nSatunnaiset esteet generoitu. Valitse seuraavaksi algoritmi.")
                    print(f"Esteiden määrä: {len(grid.obstacles)}")

                elif event.key == pygame.K_SPACE:
                    placement_mode = None

                    if grid.start is None or grid.goal is None:
                        print("Aseta ensin lähtöpiste ja kohdepiste.")
                    elif selected_algorithm is None:
                        print("Valitse ensin algoritmi: Dijkstra, A* tai D* Lite.")
                    else:
                        result = run_selected_algorithm(
                            grid,
                            selected_algorithm,
                            grid.start,
                            grid.goal
                        )

                        last_result = result
                        path = result["path"]
                        visited = result["visited_order"]
                        vehicle_position = None

                        print_result(result)
                        animate_search(
                            screen,
                            grid,
                            visited,
                            path,
                            buttons=buttons,
                            font=font,
                            selected_algorithm=selected_algorithm,
                            placement_mode=placement_mode,
                            auto_obstacle_count=auto_obstacle_count,
                            auto_obstacle_positions=visible_auto_obstacle_positions,
                        )

                elif event.key == pygame.K_RETURN:
                    placement_mode = None

                    if not path or last_result is None or not last_result.get("success", False):
                        print("Laske ensin onnistunut reitti.")
                    else:
                        if selected_algorithm == "dstar_lite":
                            path, visited, vehicle_position, visible_auto_obstacle_positions = animate_vehicle_with_dstar_lite(
                                screen,
                                grid,
                                path,
                                visited,
                                last_result,
                                buttons=buttons,
                                font=font,
                                auto_obstacle_count=auto_obstacle_count
                            )
                        else:
                            path, visited, vehicle_position, visible_auto_obstacle_positions = animate_vehicle_with_manual_obstacles(
                                screen,
                                grid,
                                path,
                                visited,
                                selected_algorithm,
                                last_result,
                                buttons=buttons,
                                font=font,
                                auto_obstacle_count=auto_obstacle_count
                            )

        update_button_states(buttons, grid, selected_algorithm, path, last_result, auto_obstacle_count, placement_mode)

        draw_grid(
            screen,
            grid,
            path=path,
            visited=visited,
            vehicle_position=vehicle_position,
            buttons=buttons,
            font=font,
            selected_algorithm=selected_algorithm,
            placement_mode=placement_mode,
            auto_obstacle_count=auto_obstacle_count,
            auto_obstacle_positions=visible_auto_obstacle_positions,
        )
        pygame.display.flip()

        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
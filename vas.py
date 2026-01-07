import random
from enum import Enum, auto
from typing import List, Tuple, Optional
import csv
import matplotlib.pyplot as plt

import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog

from PIL import Image, ImageTk 

# ===============================
# Parametri simulacije (default)
# ===============================

GRID_WIDTH = 30
GRID_HEIGHT = 30

INITIAL_RABBITS = 50
INITIAL_FOXES = 10

MAX_RESOURCE = 5
RESOURCE_REGEN = 1

# zečevi
RABBIT_START_ENERGY = 5
RABBIT_MOVE_COST = 2 #2
RABBIT_ENERGY_FROM_FOOD = 3
RABBIT_REPRODUCTION_THRESHOLD = 15 #10
RABBIT_MAX_AGE = 40
# dodatni troškovi za rizične zečeve
RABBIT_MOVE_COST_RISKY = RABBIT_MOVE_COST + 1
RABBIT_REPRODUCTION_THRESHOLD_RISKY = RABBIT_REPRODUCTION_THRESHOLD + 3


# lisice
FOX_START_ENERGY = 10
FOX_MOVE_COST = 1
FOX_ENERGY_FROM_PREY = 15 #8
FOX_REPRODUCTION_THRESHOLD = 20
FOX_MAX_AGE = 60

PERCEPTION_RADIUS_RABBIT = 2
PERCEPTION_RADIUS_FOX = 3

SIMULATION_STEPS = 300

def prompt_simulation_parameters():
    """
    Otvara jednostavne GUI dijaloge za unos početnog broja zečeva, lisica
    i dimenzija mreže. Ako korisnik pritisne Cancel, ostaju zadane vrijednosti.
    """
    global INITIAL_RABBITS, INITIAL_FOXES, GRID_WIDTH, GRID_HEIGHT

    root = tk.Tk()
    root.withdraw()  # sakrij glavni prozor

    try:
        r = simpledialog.askinteger(
            "Parametri simulacije",
            "Početni broj zečeva:",
            initialvalue=INITIAL_RABBITS,
            minvalue=1,
            maxvalue=500,
            parent=root,
        )
        if r is not None:
            INITIAL_RABBITS = r

        f = simpledialog.askinteger(
            "Parametri simulacije",
            "Početni broj lisica:",
            initialvalue=INITIAL_FOXES,
            minvalue=1,
            maxvalue=200,
            parent=root,
        )
        if f is not None:
            INITIAL_FOXES = f

        w = simpledialog.askinteger(
            "Parametri simulacije",
            "Širina mreže (GRID_WIDTH):",
            initialvalue=GRID_WIDTH,
            minvalue=5,
            maxvalue=100,
            parent=root,
        )
        if w is not None:
            GRID_WIDTH = w

        h = simpledialog.askinteger(
            "Parametri simulacije",
            "Visina mreže (GRID_HEIGHT):",
            initialvalue=GRID_HEIGHT,
            minvalue=5,
            maxvalue=100,
            parent=root,
        )
        if h is not None:
            GRID_HEIGHT = h
    finally:
        root.destroy()

# ===============================
# Stanja i tipovi
# ===============================

class RabbitState(Enum):
    TRAZI_HRANU = auto()
    BIJEG = auto()
    RAZMNOZAVANJE = auto()
    MIGRACIJA = auto()
    ODMOR = auto()
    MRTAV = auto()


class FoxState(Enum):
    PATROLIRANJE = auto()
    POTJERA = auto()
    HRANJENJE = auto()
    RAZMNOZAVANJE = auto()
    MIGRACIJA = auto()
    GLADOVANJE = auto()
    MRTAV = auto()


class RabbitType(Enum):
    OPREZNI = auto()
    RIZICNI = auto()

# ===============================
# Jednostavne poruke (FIPA-like)
# ===============================

class Performative(Enum):
    INFORM = auto()


class Message:
    def __init__(self, sender_id: int, receiver_id: Optional[int],
                 performative: Performative, content: dict):
        self.sender_id = sender_id
        self.receiver_id = receiver_id  # None = broadcast
        self.performative = performative
        self.content = content  # npr. {"type": "prey_seen", "pos": (x, y)}


# globalna "poštanska kutija" za poruke među lisicama
FOX_MESSAGE_BOARD: List[Message] = []

# ===============================
# Okolina (2D mreža)
# ===============================

class Patch:
    """
    Zakrpa s količinom biljne biomase (hrana za zečeve).
    """
    def __init__(self, initial_resource: Optional[int] = None):
        if initial_resource is None:
            self.resource = random.randint(0, MAX_RESOURCE)
        else:
            self.resource = initial_resource

    def regen(self):
        self.resource = min(MAX_RESOURCE, self.resource + RESOURCE_REGEN)


class Environment:
    """
    2D diskretna mreža zakrpa; služi kao zajednička baza znanja za agente.
    """
    def __init__(self, width: int, height: int, fragmented: bool = False):
        self.width = width
        self.height = height
        self.grid = [[Patch() for _ in range(height)] for _ in range(width)]

        # jednostavno "fragmentirano" stanište: vertikalna barijera bez resursa
        if fragmented:
            mid = width // 2
            for x in range(mid - 1, mid + 2):
                if 0 <= x < width:
                    for y in range(height):
                        self.grid[x][y] = Patch(initial_resource=0)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def neighbors(self, x: int, y: int, radius: int = 1) -> List[Tuple[int, int]]:
        coords = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if self.in_bounds(nx, ny):
                    coords.append((nx, ny))
        return coords

    def get_patch(self, x: int, y: int) -> Patch:
        return self.grid[x][y]

    def regen_resources(self):
        for x in range(self.width):
            for y in range(self.height):
                self.grid[x][y].regen()

# ===============================
# Bazna klasa agenta
# ===============================

class AgentBase:
    """
    Sadrži zajedničke atribute (baza znanja na razini jedinke).
    """
    def __init__(self, x: int, y: int, energy: int, max_age: int):
        self.x = x
        self.y = y
        self.energy = energy
        self.age = 0
        self.max_age = max_age
        # jednostavna baza znanja / beliefs
        self.beliefs = {
            "best_food_patch": None,   # zadnja zapamćena dobra hrana
            "danger_zone": None,       # zadnje viđena lisica / područje opasnosti
        }

    def is_dead(self) -> bool:
        return self.energy <= 0 or self.age >= self.max_age

    def move_random(self, env: Environment, radius: int = 1):
        neigh = env.neighbors(self.x, self.y, radius=radius)
        if neigh:
            self.x, self.y = random.choice(neigh)

    def move_towards(self, env: Environment, tx: int, ty: int):
        dx = 0 if tx == self.x else (1 if tx > self.x else -1)
        dy = 0 if ty == self.y else (1 if ty > self.y else -1)
        nx, ny = self.x + dx, self.y + dy
        if env.in_bounds(nx, ny):
            self.x, self.y = nx, ny

# ===============================
# Agent Zec
# ===============================

class Rabbit(AgentBase):
    def __init__(self, x: int, y: int, r_type: RabbitType):
        super().__init__(x, y, RABBIT_START_ENERGY, RABBIT_MAX_AGE)
        self.state = RabbitState.TRAZI_HRANU
        self.r_type = r_type
        # individualni parametri ovisno o strategiji
               # individualni parametri ovisno o strategiji
        if self.r_type == RabbitType.RIZICNI:
            self.move_cost = RABBIT_MOVE_COST_RISKY
            self.reproduction_threshold = RABBIT_REPRODUCTION_THRESHOLD_RISKY
        else:
            self.move_cost = RABBIT_MOVE_COST
            self.reproduction_threshold = RABBIT_REPRODUCTION_THRESHOLD
    
    def perceive(self, env: Environment, foxes: List["Fox"]) -> dict:
        """
        Lokalna baza znanja:
        - mapa hrane u susjedstvu
        - prisutnost lisica u radijusu
        """
        info = {
            "best_food_patch": None,
            "fox_nearby": False,
            "fox_pos": None,
        }

        best_food = -1
        for nx, ny in env.neighbors(self.x, self.y, radius=PERCEPTION_RADIUS_RABBIT):
            r = env.get_patch(nx, ny).resource
            if r > best_food:
                best_food = r
                info["best_food_patch"] = (nx, ny)

        for f in foxes:
            if abs(f.x - self.x) <= PERCEPTION_RADIUS_RABBIT and abs(f.y - self.y) <= PERCEPTION_RADIUS_RABBIT:
                info["fox_nearby"] = True
                info["fox_pos"] = (f.x, f.y)
                break

        # ažuriranje beliefs
        if info["best_food_patch"] is not None:
            self.beliefs["best_food_patch"] = info["best_food_patch"]
        if info["fox_pos"] is not None:
            self.beliefs["danger_zone"] = info["fox_pos"]

        return info

    def update_state(self, info: dict):
        if self.is_dead():
            self.state = RabbitState.MRTAV
            return

        if info["fox_nearby"] and self.energy > 0:
            self.state = RabbitState.BIJEG
        elif self.energy >= self.reproduction_threshold:
            self.state = RabbitState.RAZMNOZAVANJE

        elif self.energy < 2 and self.r_type == RabbitType.OPREZNI:
            # oprezni češće odmaraju kad su blizu gladi
            self.state = RabbitState.ODMOR
        else:
            if info["best_food_patch"] is None and self.beliefs["best_food_patch"] is None:
                self.state = RabbitState.MIGRACIJA
            else:
                self.state = RabbitState.TRAZI_HRANU

    def act(self, env: Environment, rabbits: List["Rabbit"], foxes: List["Fox"]) -> List["Rabbit"]:
        """
        Jedan diskretni korak ponašanja zeca. Vraća listu novih zečeva.
        """
        self.age += 1
        self.energy -= self.move_cost


        info = self.perceive(env, foxes)
        self.update_state(info)

        new_rabbits: List[Rabbit] = []

        if self.state == RabbitState.MRTAV:
            return new_rabbits

        if self.state == RabbitState.TRAZI_HRANU:
            # koristi trenutno viđenu ili zapamćenu najbolju hranu
            target = info["best_food_patch"] or self.beliefs["best_food_patch"]

            if target:
                self.move_towards(env, *target)
            else:
                self.move_random(env)

            patch = env.get_patch(self.x, self.y)
            eaten = min(patch.resource, 1)
            patch.resource -= eaten

            # oprezni zečevi mogu jesti isto ili malo manje; ovdje ostavljamo isto
            if self.r_type == RabbitType.OPREZNI:
                eaten = eaten
            self.energy += eaten * RABBIT_ENERGY_FROM_FOOD

        elif self.state == RabbitState.BIJEG:
            # različite strategije bijega
            if self.r_type == RabbitType.OPREZNI and self.beliefs["danger_zone"] is not None:
                fx, fy = self.beliefs["danger_zone"]
                dx = self.x - fx
                dy = self.y - fy
                target_x = self.x + (1 if dx >= 0 else -1)
                target_y = self.y + (1 if dy >= 0 else -1)
                if env.in_bounds(target_x, target_y):
                    self.x, self.y = target_x, target_y
                else:
                    self.move_random(env)
            else:
                # rizični ili bez informacije bježe nasumično
                self.move_random(env)

            self.energy -= 1

        elif self.state == RabbitState.RAZMNOZAVANJE:
            neigh = env.neighbors(self.x, self.y, radius=1)
            if neigh and self.energy >= RABBIT_REPRODUCTION_THRESHOLD:
                nx, ny = random.choice(neigh)
                # dijete nasljeđuje tip roditelja
                new_rabbits.append(Rabbit(nx, ny, self.r_type))
                self.energy //= 2

        elif self.state == RabbitState.MIGRACIJA:
            # širi radijus kretanja – promjena fragmenta staništa
            self.move_random(env, radius=2)
            self.energy -= 1

        elif self.state == RabbitState.ODMOR:
            # ne miče se, minimalna potrošnja
            pass

        return new_rabbits

# ===============================
# Agent Lisica
# ===============================

class Fox(AgentBase):
    _id_counter = 0

    def __init__(self, x: int, y: int):
        super().__init__(x, y, FOX_START_ENERGY, FOX_MAX_AGE)
        self.state = FoxState.PATROLIRANJE
        # jedinstveni ID lisice za poruke
        self.id = Fox._id_counter
        Fox._id_counter += 1

    def receive_messages(self) -> List[Message]:
        """
        Dohvati sve poruke namijenjene ovoj lisici (direct ili broadcast).
        """
        received = []
        for m in FOX_MESSAGE_BOARD:
            if m.receiver_id is None or m.receiver_id == self.id:
                received.append(m)
        return received

    def perceive(self, env: Environment, rabbits: List[Rabbit]) -> dict:
        """
        Lokalno znanje lisice:
        - najbliži zec u radijusu
        - broj zečeva u okolini (gustoća plijena)
        """
        info = {
            "nearest_rabbit": None,
            "prey_in_range": False,
            "prey_count": 0,
        }

        best_dist = 999
        for r in rabbits:
            dx = abs(r.x - self.x)
            dy = abs(r.y - self.y)
            d = max(dx, dy)
            if d <= PERCEPTION_RADIUS_FOX:
                info["prey_in_range"] = True
                info["prey_count"] += 1
                if d < best_dist:
                    best_dist = d
                    info["nearest_rabbit"] = r

        # ako vidi plijen, šalje INFORM poruku o njegovoj poziciji (broadcast)
        if info["prey_in_range"] and info["nearest_rabbit"] is not None:
            msg = Message(
                sender_id=self.id,
                receiver_id=None,
                performative=Performative.INFORM,
                content={"type": "prey_seen",
                         "pos": (info["nearest_rabbit"].x,
                                 info["nearest_rabbit"].y)},
            )
            FOX_MESSAGE_BOARD.append(msg)
            print(f"[SEND] Lisica {self.id} šalje INFORM o plijenu na {msg.content['pos']}")

        return info

    def update_state(self, info: dict):
        if self.is_dead():
            self.state = FoxState.MRTAV
            return

        if self.energy <= 3:
            self.state = FoxState.GLADOVANJE
        elif info["prey_in_range"]:
            self.state = FoxState.POTJERA
        elif self.energy >= FOX_REPRODUCTION_THRESHOLD:
            self.state = FoxState.RAZMNOZAVANJE
        elif self.energy < 6:
            self.state = FoxState.MIGRACIJA
        else:
            self.state = FoxState.PATROLIRANJE

    def act(self, env: Environment, rabbits: List[Rabbit]) -> Tuple[List["Fox"], List[Rabbit]]:
        """
        Jedan diskretni korak lisice. Vraća: nove lisice, listu pojedenih zečeva.
        """
        self.age += 1
        self.energy -= FOX_MOVE_COST

        info = self.perceive(env, rabbits)
        self.update_state(info)

        # obrada poruka (FIPA-like INFORM)
        received = self.receive_messages()
        if received:
            print(f"[RECV] Lisica {self.id} primila {len(received)} INFORM poruka")
        prey_hint_pos = None
        for m in received:
            if m.performative == Performative.INFORM and m.content.get("type") == "prey_seen":
                prey_hint_pos = m.content.get("pos")

        new_foxes: List[Fox] = []
        eaten_rabbits: List[Rabbit] = []

        if self.state == FoxState.MRTAV:
            return new_foxes, eaten_rabbits

        if self.state == FoxState.PATROLIRANJE:
            # ako nema lokalnog plijena, ali postoji informacija od drugih lisica,
            # kreći se prema toj poziciji umjesto nasumično
            if not info["prey_in_range"] and prey_hint_pos is not None:
                tx, ty = prey_hint_pos
                self.move_towards(env, tx, ty)
            else:
                self.move_random(env)

        elif self.state == FoxState.POTJERA:
            target = info["nearest_rabbit"]
            if target:
                self.move_towards(env, target.x, target.y)
                # ako dođe na istu ćeliju -> predacija
                if self.x == target.x and self.y == target.y:
                    if random.random() < 0.9: #0.7
                        eaten_rabbits.append(target)
                        self.energy += FOX_ENERGY_FROM_PREY
                        self.state = FoxState.HRANJENJE

        if self.state == FoxState.HRANJENJE:
            # nakon hranjenja može ići u razmnožavanje ili patrolu
            if self.energy >= FOX_REPRODUCTION_THRESHOLD:
                self.state = FoxState.RAZMNOZAVANJE
            else:
                self.state = FoxState.PATROLIRANJE

        elif self.state == FoxState.RAZMNOZAVANJE:
            neigh = env.neighbors(self.x, self.y, radius=1)
            if neigh and self.energy >= FOX_REPRODUCTION_THRESHOLD:
                nx, ny = random.choice(neigh)
                new_foxes.append(Fox(nx, ny))
                self.energy //= 2
            self.state = FoxState.PATROLIRANJE

        elif self.state == FoxState.MIGRACIJA:
            # veći skok – „traži“ novo područje s više plijena
            self.move_random(env, radius=2)

        elif self.state == FoxState.GLADOVANJE:
            # minimalno kretanje, velika šansa smrti
            if random.random() < 0.5:
                self.move_random(env)
            self.energy -= 1

        return new_foxes, eaten_rabbits

# ===============================
# Inicijalizacija populacije
# ===============================

def initialize_population(env: Environment, init_rabbits: int, init_foxes: int) -> Tuple[List[Rabbit], List[Fox]]:
    rabbits: List[Rabbit] = []
    foxes: List[Fox] = []

    for i in range(init_rabbits):
        x = random.randrange(env.width)
        y = random.randrange(env.height)
        # pola oprezni, pola rizični
        r_type = RabbitType.OPREZNI if i % 2 == 0 else RabbitType.RIZICNI
        rabbits.append(Rabbit(x, y, r_type))

    for _ in range(init_foxes):
        x = random.randrange(env.width)
        y = random.randrange(env.height)
        foxes.append(Fox(x, y))

    return rabbits, foxes

# ===============================
# GENERIČNA SIMULACIJA SCENARIJA
# ===============================

def simulate_scenario(
    steps: int,
    grid_width: int,
    grid_height: int,
    init_rabbits: int,
    init_foxes: int,
    resource_regen: int,
    fragmented: bool = False,
):
    """
    Pokreni simulaciju za zadane parametre i vrati:
    - serije ukupnog broja zečeva i lisica
    - serije broja opreznih i rizičnih zečeva po koraku
    """
    global RESOURCE_REGEN
    RESOURCE_REGEN = resource_regen

    env = Environment(grid_width, grid_height, fragmented=fragmented)
    rabbits, foxes = initialize_population(env, init_rabbits, init_foxes)

    rabbits_counts: List[int] = []
    foxes_counts: List[int] = []
    cautious_counts: List[int] = []   # OPREZNI
    risky_counts: List[int] = []      # RIZICNI

    for step in range(steps):
        env.regen_resources()

        # zečevi
        new_rabbits: List[Rabbit] = []
        alive_rabbits: List[Rabbit] = []

        for r in rabbits:
            offspring = r.act(env, rabbits, foxes)
            new_rabbits.extend(offspring)

        for r in rabbits:
            if not r.is_dead() and r.state != RabbitState.MRTAV:
                alive_rabbits.append(r)

        alive_rabbits.extend(new_rabbits)
        rabbits = alive_rabbits

        # lisice
        new_foxes: List[Fox] = []
        alive_foxes: List[Fox] = []
        eaten_rabbits: List[Rabbit] = []

        for f in foxes:
            off, eaten = f.act(env, rabbits)
            new_foxes.extend(off)
            eaten_rabbits.extend(eaten)

        rabbits = [r for r in rabbits if r not in eaten_rabbits]

        for f in foxes:
            if not f.is_dead() and f.state != FoxState.MRTAV:
                alive_foxes.append(f)
        alive_foxes.extend(new_foxes)
        foxes = alive_foxes

        # agregacija
        rabbits_counts.append(len(rabbits))
        foxes_counts.append(len(foxes))
        cautious_counts.append(sum(1 for r in rabbits if r.r_type == RabbitType.OPREZNI))
        risky_counts.append(sum(1 for r in rabbits if r.r_type == RabbitType.RIZICNI))

        # kraj koraka: brišemo poruke (jedan komunikacijski "round")
        FOX_MESSAGE_BOARD.clear()

        if len(rabbits) == 0 or len(foxes) == 0:
            break

    return rabbits_counts, foxes_counts, cautious_counts, risky_counts

# ===============================
# RUN VIŠE SCENARIJA I USPoredba
# ===============================

def run_scenarios():
    """
    Primjer: tri scenarija za seminarski.
    1) Homogeno stanište, osnovni RESOURCE_REGEN
    2) Fragmentirano stanište (barijera bez resursa)
    3) Pojačana regeneracija resursa
    """
    scenarios = [
        {
            "name": "Homogeno",
            "fragmented": False,
            "resource_regen": 1,
            "color_rabbit": "green",
            "color_fox": "red",
        },
        {
            "name": "Fragmentirano",
            "fragmented": True,
            "resource_regen": 1,
            "color_rabbit": "darkgreen",
            "color_fox": "darkred",
        },
        {
            "name": "Visoka regeneracija",
            "fragmented": False,
            "resource_regen": 2,
            "color_rabbit": "lime",
            "color_fox": "orange",
        },
    ]

    plt.figure(figsize=(10, 6))

    for scen in scenarios:
        rabbits_counts, foxes_counts, _, _ = simulate_scenario(
            steps=SIMULATION_STEPS,
            grid_width=GRID_WIDTH,
            grid_height=GRID_HEIGHT,
            init_rabbits=INITIAL_RABBITS,
            init_foxes=INITIAL_FOXES,
            resource_regen=scen["resource_regen"],
            fragmented=scen["fragmented"],
        )

        steps_range = list(range(len(rabbits_counts)))

        plt.plot(
            steps_range,
            rabbits_counts,
            label=f"Zečevi - {scen['name']}",
            color=scen["color_rabbit"],
            linestyle="-",
        )
        plt.plot(
            steps_range,
            foxes_counts,
            label=f"Lisice - {scen['name']}",
            color=scen["color_fox"],
            linestyle="--",
        )

    plt.xlabel("Korak simulacije")
    plt.ylabel("Broj jedinki")
    plt.title("Dinamika populacija u različitim scenarijima")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("scenariji_populacije.png", dpi=300)
    plt.close()

# ===============================
# Jedan scenarij + CSV
# ===============================

def simulate_and_log(csv_filename="populacije.csv", png_filename="populacije.png"):
    rabbits_counts, foxes_counts, _, _ = simulate_scenario(
        steps=SIMULATION_STEPS,
        grid_width=GRID_WIDTH,
        grid_height=GRID_HEIGHT,
        init_rabbits=INITIAL_RABBITS,
        init_foxes=INITIAL_FOXES,
        resource_regen=RESOURCE_REGEN,
        fragmented=False,
    )

    steps = list(range(len(rabbits_counts)))

    with open(csv_filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["step", "rabbits", "foxes"])
        for s, r_count, f_count in zip(steps, rabbits_counts, foxes_counts):
            writer.writerow([s, r_count, f_count])

    plt.figure(figsize=(8, 5))
    plt.plot(steps, rabbits_counts, label="Zečevi", color="green")
    plt.plot(steps, foxes_counts, label="Lisice", color="red")
    plt.xlabel("Korak simulacije")
    plt.ylabel("Broj jedinki")
    plt.title("Dinamika populacija grabežljivac–plijen (jedan scenarij)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(png_filename, dpi=300)
    plt.close()

def simulate_and_log_strategies(
    csv_filename="strategije_zeceva.csv",
    png_filename="strategije_zeceva.png",
):
    rabbits_counts, foxes_counts, cautious_counts, risky_counts = simulate_scenario(
        steps=SIMULATION_STEPS,
        grid_width=GRID_WIDTH,
        grid_height=GRID_HEIGHT,
        init_rabbits=INITIAL_RABBITS,
        init_foxes=INITIAL_FOXES,
        resource_regen=RESOURCE_REGEN,
        fragmented=False,
    )

    steps = list(range(len(rabbits_counts)))

    # CSV s odvojenim tipovima zečeva
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["step", "rabbits_total", "foxes",
                         "rabbits_oprezni", "rabbits_rizicni"])
        for s, rt, ft, rc, rr in zip(
            steps, rabbits_counts, foxes_counts, cautious_counts, risky_counts
        ):
            writer.writerow([s, rt, ft, rc, rr])

    # Dijagram strategija
    plt.figure(figsize=(8, 5))
    plt.plot(steps, cautious_counts, label="Oprezni zečevi", color="blue")
    plt.plot(steps, risky_counts, label="Rizični zečevi", color="orange")
    plt.plot(steps, rabbits_counts, label="Svi zečevi", color="green", linestyle="--")
    plt.xlabel("Korak simulacije")
    plt.ylabel("Broj jedinki")
    plt.title("Dinamika strategija plijena (oprezni vs. rizični)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(png_filename, dpi=300)
    plt.close()

def main_gui():
    global INITIAL_RABBITS, INITIAL_FOXES, GRID_WIDTH, GRID_HEIGHT

    root = tk.Tk()
    root.title("Simulacija grabežljivac–plijen")

    notebook = ttk.Notebook(root)
    frame_sim = ttk.Frame(notebook)
    frame_analysis = ttk.Frame(notebook)
    

    notebook.add(frame_sim, text="Simulacija")
    notebook.add(frame_analysis, text="Analiza")
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

    params_frame = ttk.LabelFrame(frame_sim, text="Parametri simulacije")
    params_frame.pack(fill="both", expand=True, padx=10, pady=10)

    ttk.Label(params_frame, text="Početni broj zečeva:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    entry_rabbits = ttk.Entry(params_frame, width=10)
    entry_rabbits.insert(0, str(INITIAL_RABBITS))
    entry_rabbits.grid(row=0, column=1, padx=5, pady=5)

    ttk.Label(params_frame, text="Početni broj lisica:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
    entry_foxes = ttk.Entry(params_frame, width=10)
    entry_foxes.insert(0, str(INITIAL_FOXES))
    entry_foxes.grid(row=1, column=1, padx=5, pady=5)

    ttk.Label(params_frame, text="Širina mreže (GRID_WIDTH):").grid(row=2, column=0, sticky="w", padx=5, pady=5)
    entry_width = ttk.Entry(params_frame, width=10)
    entry_width.insert(0, str(GRID_WIDTH))
    entry_width.grid(row=2, column=1, padx=5, pady=5)

    ttk.Label(params_frame, text="Visina mreže (GRID_HEIGHT):").grid(row=3, column=0, sticky="w", padx=5, pady=5)
    entry_height = ttk.Entry(params_frame, width=10)
    entry_height.insert(0, str(GRID_HEIGHT))
    entry_height.grid(row=3, column=1, padx=5, pady=5)

    status_label = ttk.Label(frame_sim, text="Unesite parametre i pokrenite simulaciju.", foreground="blue")
    status_label.pack(padx=10, pady=5)

    def run_all():
        nonlocal entry_rabbits, entry_foxes, entry_width, entry_height
        global INITIAL_RABBITS, INITIAL_FOXES, GRID_WIDTH, GRID_HEIGHT

        try:
            INITIAL_RABBITS = int(entry_rabbits.get())
            INITIAL_FOXES = int(entry_foxes.get())
            GRID_WIDTH = int(entry_width.get())
            GRID_HEIGHT = int(entry_height.get())
        except ValueError:
            status_label.config(text="Neispravan unos. Koristi cijele brojeve.", foreground="red")
            return

        status_label.config(text="Simulacija se izvršava, pričekajte...", foreground="black")
        root.update_idletasks()

        simulate_and_log()
        simulate_and_log_strategies()
        run_scenarios()

        status_label.config(
            text="Simulacija završena. Grafovi i CSV datoteke su spremljeni u radni direktorij.",
            foreground="green",
        )

    run_button = ttk.Button(frame_sim, text="Pokreni simulaciju", command=run_all)
    run_button.pack(pady=10)
    def open_image_window(title, filename):
        max_size = (800, 600)  # ili npr. (700, 500)

        win = tk.Toplevel(root)
        win.title(title)

        img = Image.open(filename)
        img.thumbnail(max_size)  # smanji da stane u max_size, čuva omjer

        photo = ImageTk.PhotoImage(img)
        label = ttk.Label(win, image=photo)
        label.image = photo  # referenca
        label.pack()

    # Gumbi u tabu Analiza
    ttk.Button(
        frame_analysis,
        text="Prikaži dinamiku populacija",
        command=lambda: open_image_window("Dinamika populacija", "populacije.png"),
    ).pack(padx=10, pady=10)

    ttk.Button(
        frame_analysis,
        text="Prikaži strategije zečeva",
        command=lambda: open_image_window("Strategije zečeva", "strategije_zeceva.png"),
    ).pack(padx=10, pady=10)

    ttk.Button(
        frame_analysis,
        text="Prikaži scenarije populacije",
        command=lambda: open_image_window("Scenariji populacije", "scenariji_populacije.png"),
    ).pack(padx=10, pady=10)

    root.mainloop()


if __name__ == "__main__":
    main_gui()



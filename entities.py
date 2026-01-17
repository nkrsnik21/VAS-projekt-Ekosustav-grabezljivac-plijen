import random
from enum import Enum, auto


class PreyState(Enum):
    RESTING = auto()
    MOVING = auto()
    FEEDING = auto()
    REPRODUCING = auto()
    DEAD = auto()


class PredatorState(Enum):
    RESTING = auto()
    SEARCHING = auto()
    HUNTING = auto()
    REPRODUCING = auto()
    DEAD = auto()


# Tablica prijelaza za plijen
PREY_TRANSITIONS = {
    PreyState.RESTING: {
        "predator_nearby": PreyState.MOVING,
        "can_reproduce": PreyState.REPRODUCING,
        "hungry_and_food": PreyState.FEEDING,
        "default": PreyState.RESTING,
    },
    PreyState.MOVING: {
        "can_reproduce": PreyState.REPRODUCING,
        "hungry_and_food": PreyState.FEEDING,
        "default": PreyState.MOVING,
    },
    PreyState.FEEDING: {
        "predator_nearby": PreyState.MOVING,
        "can_reproduce": PreyState.REPRODUCING,
        "default": PreyState.RESTING,
    },
    PreyState.REPRODUCING: {
        "predator_nearby": PreyState.MOVING,
        "default": PreyState.RESTING,
    },
}


# Tablica prijelaza za predatora
PREDATOR_TRANSITIONS = {
    PredatorState.RESTING: {
        "can_reproduce": PredatorState.REPRODUCING,
        "hungry_and_prey": PredatorState.HUNTING,
        "prey_nearby": PredatorState.SEARCHING,
        "default": PredatorState.RESTING,
    },
    PredatorState.SEARCHING: {
        "can_reproduce": PredatorState.REPRODUCING,
        "hungry_and_prey": PredatorState.HUNTING,
        "no_prey_bad_weather": PredatorState.RESTING,
        "default": PredatorState.SEARCHING,
    },
    PredatorState.HUNTING: {
        "can_reproduce": PredatorState.REPRODUCING,
        "default": PredatorState.SEARCHING,
    },
    PredatorState.REPRODUCING: {
        "default": PredatorState.RESTING,
    },
}


class Prey:
    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        energy: float = 12.0,
        age: int = 0,
        reproduction_threshold: float = 12.0,
        max_age: int = 80,
    ):
        self.name = name
        self.x = x
        self.y = y
        self.energy = energy
        self.age = age
        self.alive = True
        self.reproduction_threshold = reproduction_threshold
        self.max_age = max_age
        self.state = PreyState.RESTING 

    def decide_state(self, local_resources: float, predator_nearby: bool) -> PreyState:
        if not self.alive:
            self.state = PreyState.DEAD
            return self.state

        can_reproduce = (
            self.energy >= self.reproduction_threshold
            and (not predator_nearby or random.random() < 0.3)
        )
        hungry_and_food = self.energy < 6.0 and local_resources > 0.5
        predator_threat = predator_nearby and self.energy > 1.0

        rules = PREY_TRANSITIONS.get(self.state, PREY_TRANSITIONS[PreyState.RESTING])

        if predator_threat:
            self.state = rules.get("predator_nearby", self.state)
        elif can_reproduce:
            self.state = rules.get("can_reproduce", self.state)
        elif hungry_and_food:
            self.state = rules.get("hungry_and_food", self.state)
        else:
            self.state = rules.get("default", self.state)

        return self.state

    def decide_action(self, local_resources: float, predator_nearby: bool) -> str:
        state = self.decide_state(local_resources, predator_nearby)
        if state == PreyState.REPRODUCING:
            return "reproduce"
        if state == PreyState.FEEDING:
            return "feed"
        if state == PreyState.MOVING:
            return "move"
        if state == PreyState.RESTING:
            return "rest"
        return "dead"

    def move(self, width: int, height: int):
        dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        self.x = max(0, min(width - 1, self.x + dx))
        self.y = max(0, min(height - 1, self.y + dy))
        self.energy -= 0.8

    def rest(self):
        self.energy -= 0.2

    def after_feed(self):
        self.energy -= 0.1

    def try_reproduce(self):
        if self.energy < self.reproduction_threshold:
            return None
        self.energy *= 0.5
        child = Prey(
            name=f"{self.name}_child{random.randint(1, 9999)}",
            x=self.x,
            y=self.y,
            energy=self.energy,
            age=0,
            reproduction_threshold=self.reproduction_threshold,
            max_age=self.max_age,
        )
        return child

    def age_and_check_death(self):
        self.age += 1
        if self.energy <= 0 or self.age >= self.max_age:
            self.alive = False


class Predator:
    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        energy: float = 14.0,
        age: int = 0,
        reproduction_threshold: float = 14.0,
        max_age: int = 100,
    ):
        self.name = name
        self.x = x
        self.y = y
        self.energy = energy
        self.age = age
        self.alive = True
        self.reproduction_threshold = reproduction_threshold
        self.max_age = max_age
        self.state = PredatorState.RESTING 

    def decide_state(self, prey_nearby: bool, weather_factor: float) -> PredatorState:
        if not self.alive:
            self.state = PredatorState.DEAD
            return self.state

        can_reproduce = self.energy >= self.reproduction_threshold
        hungry_and_prey = self.energy < 9.0 and prey_nearby
        no_prey_bad_weather = (not prey_nearby) and weather_factor < 0.8 and random.random() < 0.5

        rules = PREDATOR_TRANSITIONS.get(
            self.state, PREDATOR_TRANSITIONS[PredatorState.RESTING]
        )

        if can_reproduce:
            self.state = rules.get("can_reproduce", self.state)
        elif hungry_and_prey:
            self.state = rules.get("hungry_and_prey", self.state)
        elif prey_nearby:
            self.state = rules.get("prey_nearby", self.state)
        elif no_prey_bad_weather:
            self.state = rules.get("no_prey_bad_weather", self.state)
        else:
            self.state = rules.get("default", self.state)

        return self.state

    def decide_action(self, prey_nearby: bool, weather_factor: float) -> str:
        state = self.decide_state(prey_nearby, weather_factor)
        if state == PredatorState.REPRODUCING:
            return "reproduce"
        if state == PredatorState.HUNTING:
            return "hunt"
        if state == PredatorState.SEARCHING:
            return "search"
        if state == PredatorState.RESTING:
            return "rest"
        return "dead"

    def move(self, width: int, height: int):
        dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        self.x = max(0, min(width - 1, self.x + dx))
        self.y = max(0, min(height - 1, self.y + dy))
        self.energy -= 1.2

    def rest(self):
        self.energy -= 0.4

    def after_successful_hunt(self):
        self.energy += 8.0

    def try_reproduce(self):
        if self.energy < self.reproduction_threshold:
            return None
        self.energy *= 0.5
        child = Predator(
            name=f"{self.name}_child{random.randint(1, 9999)}",
            x=self.x,
            y=self.y,
            energy=self.energy,
            age=0,
            reproduction_threshold=self.reproduction_threshold,
            max_age=self.max_age,
        )
        return child

    def age_and_check_death(self):
        self.age += 1
        if self.energy <= 0 or self.age >= self.max_age:
            self.alive = False
import json
import random
from typing import List

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

from entities import Predator, PredatorState  


class PredatorSPAgent(Agent):
    def __init__(self, jid: str, password: str, num_predators: int):
        super().__init__(jid, password)
        self.pred_list: List[Predator] = [
            Predator(
                name=f"Predator{i}",
                x=random.randint(0, 9),
                y=random.randint(0, 9),
            )
            for i in range(1, num_predators + 1)
        ]

    class PredatorBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if not msg:
                return

            try:
                data = json.loads(msg.body)
            except Exception:
                return

            msg_type = data.get("type")

            if msg_type == "DAY_INFO":
                day = data["day"]
                coach_jid = data["coach_jid"]
                env_jid = "ekosustav2@xmpp.jp"
                width = data.get("width", 10)
                height = data.get("height", 10)
                weather_factor = data["weather_factor"]

                new_preds: List[Predator] = []

                for pred in self.agent.pred_list:
                    if not pred.alive:
                        continue

                    prey_nearby = random.random() < 0.6

                    # REAKTIVNI AUTOMAT JE U entities.Predator:
                    # decide_action -> decide_state -> stanje iz tablice prijelaza
                    action = pred.decide_action(
                        prey_nearby=prey_nearby,
                        weather_factor=weather_factor,
                    )

                    if action in ("hunt", "search"):
                        pred.move(width, height)
                        if action == "hunt":
                            req = Message(to=env_jid)
                            req.body = json.dumps(
                                {
                                    "type": "PREDATION_EVENT",
                                    "day": day,
                                    "x": pred.x,
                                    "y": pred.y,
                                    "success_prob": 0.7,
                                    "name": pred.name,
                                }
                            )
                            await self.send(req)
                    elif action == "rest":
                        pred.rest()
                    elif action == "reproduce":
                        child = pred.try_reproduce()
                        if child is not None:
                            new_preds.append(child)

                    pred.age_and_check_death()

                    reply = Message(to=coach_jid)
                    reply.body = json.dumps(
                        {
                            "type": "DAY_RESULT",
                            "role": "predator",
                            "day": day,
                            "name": pred.name,
                            "x": pred.x,
                            "y": pred.y,
                            "energy": pred.energy,
                            "age": pred.age,
                            "alive": pred.alive,
                            
                            "action": action,
                        }
                    )
                    await self.send(reply)

                self.agent.pred_list.extend(new_preds)

            elif msg_type == "PREDATION_RESULT":
                if data["success"]:
                    name = data["name"]
                    day = data["day"]
                    x = data["x"]
                    y = data["y"]

                    for pred in self.agent.pred_list:
                        if pred.name == name and pred.alive:
                            pred.after_successful_hunt()
                            break

                    prey_jid = "plijen22@xmpp.jp"
                    kill_msg = Message(to=prey_jid)
                    kill_msg.body = json.dumps(
                        {
                            "type": "PREY_KILL_NEAR",
                            "day": day,
                            "x": x,
                            "y": y,
                            "radius": 1,
                        }
                    )
                    await self.send(kill_msg)

    async def setup(self):
        print(
            f"PredatorSPAgent startao kao {str(self.jid)}, broj predatora={len(self.pred_list)}"
        )
        self.add_behaviour(self.PredatorBehaviour())
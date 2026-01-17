import asyncio
from typing import List, Dict, Any
import csv
from datetime import datetime

from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message
import json

from prey_agent import PreySPAgent
from predator_agent import PredatorSPAgent
from environment import EcosystemAgent


class EcoCoachAgent(Agent):
    def __init__(self, jid: str, password: str, iterations: int = 30):
        super().__init__(jid, password)
        self.iterations = iterations
        self.history: List[Dict[str, Any]] = []
        self.env_jid = "ekosustav2@xmpp.jp"

    class OrchestrateBehaviour(OneShotBehaviour):
        async def run(self):
            for day in range(1, self.agent.iterations + 1):
                msg = Message(to=self.agent.env_jid)
                msg.body = json.dumps({
                    "type": "NEW_DAY",
                    "day": day,
                    "coach_jid": str(self.agent.jid),
                })
                await self.send(msg)

                env_ready = None
                while not env_ready:
                    m = await self.receive(timeout=5)
                    if not m:
                        break
                    data = json.loads(m.body)
                    if data.get("type") == "ENV_READY" and data.get("day") == day:
                        env_ready = data

                if not env_ready:
                    print(f"EcoCoach: nema ENV_READY za dan {day}")
                    continue

                day_data: Dict[str, Any] = {
                    "day": day,
                    "weather": env_ready.get("weather"),
                    "weather_factor": env_ready.get("weather_factor"),
                    "agents": [],
                }

                # skupljaj DAY_RESULT poruke dok ne istekne kratki timeout
                while True:
                    m = await self.receive(timeout=1)
                    if not m:
                        break
                    data = json.loads(m.body)
                    if data.get("type") == "DAY_RESULT" and data.get("day") == day:
                        day_data["agents"].append(data)

                self.agent.history.append(day_data)

            print("EcoCoach: simulacija završena.")
            await self.agent.stop()

    async def setup(self):
        print(f"EcoCoachAgent startao kao {str(self.jid)}")
        self.add_behaviour(self.OrchestrateBehaviour())


async def run_ecosystem_simulation(
    num_prey: int,
    num_predators: int,
    iterations: int,
    resource_regen: int = 2,
    move_prob_prey: float = 0.5,
    predation_success_prob: float = 0.7,
):
    password = "test22"

    # plijen i predatori (jedan SPADE agent, više jedinki)
    prey_agent = PreySPAgent("plijen22@xmpp.jp", password, num_prey=num_prey)
    predator_agent = PredatorSPAgent("predator22@xmpp.jp", password, num_predators=num_predators)

    # proslijedi parametre na agente
    prey_agent.move_prob = move_prob_prey
    predator_agent.predation_success_prob = predation_success_prob

    # okoliš s parametriziranom regeneracijom resursa
    env_agent = EcosystemAgent(
        "ekosustav2@xmpp.jp",
        password,
        prey_jids=["plijen22@xmpp.jp"],
        predator_jids=["predator22@xmpp.jp"],
        resource_regen=resource_regen,
    )

    coach = EcoCoachAgent("agent222@xmpp.jp", password, iterations=iterations)

    await prey_agent.start(auto_register=True)
    await predator_agent.start(auto_register=True)
    await env_agent.start(auto_register=True)
    await coach.start(auto_register=True)

    while coach.is_alive():
        await asyncio.sleep(0.2)

    history = coach.history

    await prey_agent.stop()
    await predator_agent.stop()
    await env_agent.stop()
    await coach.stop()

    return history


def save_history_to_csv(
    history,
    filename=None,
    resource_regen=None,
    move_prob_prey=None,
    predation_success_prob=None,
):
    if filename is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ecosystem_history_{ts}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "day",
            "role",
            "name",
            "x",
            "y",
            "energy",
            "age",
            "alive",
            "action",
            "weather",
            "weather_factor",
            "resource_regen",
            "move_prob_prey",
            "predation_success_prob",
        ])
        for day_data in history:
            day = day_data["day"]
            weather = day_data.get("weather")
            wf = day_data.get("weather_factor")
            for agent_data in day_data["agents"]:
                writer.writerow([
                    day,
                    agent_data.get("role"),
                    agent_data.get("name"),
                    agent_data.get("x"),
                    agent_data.get("y"),
                    agent_data.get("energy"),
                    agent_data.get("age"),
                    agent_data.get("alive"),
                    agent_data.get("action"),
                    weather,
                    wf,
                    resource_regen,
                    move_prob_prey,
                    predation_success_prob,
                ])
    return filename


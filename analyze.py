import pandas as pd
import matplotlib.pyplot as plt

def load_history_csv(filename: str) -> pd.DataFrame:
    df = pd.read_csv(filename)
    return df

def plot_energy_over_time(df: pd.DataFrame):
    plt.figure(figsize=(8, 4))
    for name, sub in df.groupby("name"):
        plt.plot(sub["day"], sub["energy"], label=name)
    plt.xlabel("Dan")
    plt.ylabel("Energija")
    plt.title("Energija jedinki kroz vrijeme")
    plt.legend()
    plt.tight_layout()

def plot_population_alive(df: pd.DataFrame):
    plt.figure(figsize=(6, 4))
    alive_prey = df[df["role"] == "prey"].groupby("day")["alive"].sum()
    alive_pred = df[df["role"] == "predator"].groupby("day")["alive"].sum()
    plt.plot(alive_prey.index, alive_prey.values, label="Plijenovi")
    plt.plot(alive_pred.index, alive_pred.values, label="Predatori")
    plt.xlabel("Dan")
    plt.ylabel("Broj živih jedinki")
    plt.title("Veličina populacije kroz vrijeme")
    plt.legend()
    plt.tight_layout()

def show_plots():
    plt.show()

if __name__ == "__main__":
    df = load_history_csv("ecosystem_history_latest.csv")
    plot_energy_over_time(df)
    plot_population_alive(df)
    show_plots()

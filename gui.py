import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import asyncio
import threading

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from simulation import run_ecosystem_simulation, save_history_to_csv

current_df = None
current_csv = None
comparison_runs = [] 

def start_simulation():
    global current_df, current_csv

    try:
        num_prey = int(entry_prey.get())
        num_pred = int(entry_pred.get())
        days = int(entry_days.get())
        resource_regen = int(entry_regen.get())
        move_prob = float(entry_move_prob.get())
        pred_prob = float(entry_pred_prob.get())

        if num_prey <= 0 or num_pred <= 0 or days <= 0 or resource_regen < 0:
            raise ValueError
        if not (0.0 <= move_prob <= 1.0 and 0.0 <= pred_prob <= 1.0):
            raise ValueError
    except ValueError:
        messagebox.showerror(
            "Greška",
            "Provjeri parametre (pozitivni brojevi, vjerojatnosti u [0,1]).",
        )
        return

    btn_start.config(state="disabled")
    status_var.set("Simulacija u tijeku...")

    def worker():
        global current_df, current_csv
        try:
            history = asyncio.run(
                run_ecosystem_simulation(
                    num_prey=num_prey,
                    num_predators=num_pred,
                    iterations=days,
                    resource_regen=resource_regen,
                    move_prob_prey=move_prob,
                    predation_success_prob=pred_prob,
                )
            )
            current_csv = save_history_to_csv(
                history,
                resource_regen=resource_regen,
                move_prob_prey=move_prob,
                predation_success_prob=pred_prob,
            )
            current_df = pd.read_csv(current_csv)
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Greška", str(e)))
            root.after(0, lambda: status_var.set("Greška u simulaciji."))
            root.after(0, lambda: btn_start.config(state="normal"))
            return

        root.after(0, update_analysis_tabs)

    threading.Thread(target=worker, daemon=True).start()


def update_analysis_tabs():
    if current_df is None:
        return

    params = current_df[["resource_regen", "move_prob_prey", "predation_success_prob"]].iloc[0]
    regen = params["resource_regen"]
    move_p = params["move_prob_prey"]
    pred_p = params["predation_success_prob"]
    title_suffix = f"(regen={regen}, migracija={move_p}, predacija={pred_p})"

    # očisti stare grafove (Analiza 1–3, Podaci)
    for child in frame_analysis1.winfo_children():
        child.destroy()
    for child in frame_analysis2.winfo_children():
        child.destroy()
    for child in frame_analysis3.winfo_children():
        child.destroy()
    for child in frame_data.winfo_children():
        child.destroy()

    # ---------- Analiza 1: Oscilacije populacija ----------
    fig1 = Figure(figsize=(6, 4))
    ax1 = fig1.add_subplot(111)

    alive_prey = current_df[current_df["role"] == "prey"].groupby("day")["alive"].sum()
    alive_pred = current_df[current_df["role"] == "predator"].groupby("day")["alive"].sum()

    # dani izumiranja
    extinction_prey_days = alive_prey[alive_prey == 0].index.tolist()
    extinction_pred_days = alive_pred[alive_pred == 0].index.tolist()

    # detekcija približne stabilnosti
    N = 10
    stable = False
    if len(alive_prey) > N and len(alive_pred) > N:
        dp = alive_prey.diff().abs().tail(N).max()
        dD = alive_pred.diff().abs().tail(N).max()
        if dp <= 1 and dD <= 1:
            stable = True

    ax1.plot(alive_prey.index, alive_prey.values, label="Plijen", color="green")
    ax1.plot(alive_pred.index, alive_pred.values, label="Grabežljivac", color="red")
    ax1.set_xlabel("Dan")
    ax1.set_ylabel("Broj živih jedinki")
    ax1.set_title(f"Oscilacije populacija plijena i grabežljivaca {title_suffix}")
    ax1.legend()

    canvas1 = FigureCanvasTkAgg(fig1, master=frame_analysis1)
    canvas1.draw()
    canvas1.get_tk_widget().pack(fill="both", expand=True)

    # ---------- Analiza 2: Prosječna energija ----------
    fig2 = Figure(figsize=(6, 4))
    ax2 = fig2.add_subplot(111)

    prey_energy = current_df[current_df["role"] == "prey"].groupby("day")["energy"].mean()
    pred_energy = current_df[current_df["role"] == "predator"].groupby("day")["energy"].mean()

    # rjeđi prikaz za preglednost (svaki 5. dan)
    prey_energy = prey_energy[prey_energy.index % 5 == 0]
    pred_energy = pred_energy[pred_energy.index % 5 == 0]

    ax2.plot(prey_energy.index, prey_energy.values, label="Plijen", color="green")
    ax2.plot(pred_energy.index, pred_energy.values, label="Grabežljivac", color="red")
    ax2.set_xlabel("Dan")
    ax2.set_ylabel("Prosječna energija")
    ax2.set_title(f"Energija populacija kroz vrijeme {title_suffix}")
    ax2.legend()

    canvas2 = FigureCanvasTkAgg(fig2, master=frame_analysis2)
    canvas2.draw()
    canvas2.get_tk_widget().pack(fill="both", expand=True)

    # ---------- Analiza 3: Boxplot dobi jedinki ----------
    prey_age = current_df[current_df["role"] == "prey"]["age"]
    pred_age = current_df[current_df["role"] == "predator"]["age"]

    fig_box = Figure(figsize=(6, 4))
    ax_box = fig_box.add_subplot(111)
    ax_box.boxplot(
        [prey_age.values, pred_age.values],
        tick_labels=["Plijen", "Grabežljivac"],
    )
    ax_box.set_ylabel("Dob jedinki (dani)")
    ax_box.set_title(f"Raspodjela dobi jedinki {title_suffix}")

    canvas_box = FigureCanvasTkAgg(fig_box, master=frame_analysis3)
    canvas_box.draw()
    canvas_box.get_tk_widget().pack(fill="both", expand=True)

    # ---------- Podaci ----------
    info = tk.Text(frame_data, height=10, wrap="word")
    info.insert(
        "1.0",
        f"CSV datoteka: {current_csv}\n\n"
        f"Brzina regeneracije resursa: {regen}\n"
        f"Vjerojatnost migracije plijena: {move_p}\n"
        f"Intenzitet predacije: {pred_p}\n"
        f"Broj dana simulacije: {int(current_df['day'].max())}\n\n"
    )

    if extinction_prey_days:
        info.insert("end", f"Plijen je izumro prvi put na dan: {extinction_prey_days[0]}\n")
    else:
        info.insert("end", "Plijen nije izumro tijekom simulacije.\n")

    if extinction_pred_days:
        info.insert("end", f"Grabežljivac je izumro prvi put na dan: {extinction_pred_days[0]}\n")
    else:
        info.insert("end", "Grabežljivac nije izumro tijekom simulacije.\n")

    if stable:
        info.insert("end", f"Sustav je približno stabilan u zadnjih {N} dana (male promjene u veličini populacija).\n")
    else:
        info.insert("end", f"Sustav pokazuje značajne oscilacije u zadnjih {N} dana.\n")

    info.config(state="disabled")
    info.pack(fill="both", expand=True)

    status_var.set("Simulacija završena. Rezultati su prikazani u karticama Analiza 1–4.")


def add_csv_to_comparison():
    """Učitaj CSV s diska i dodaj njegove populacije u graf usporedbe."""
    global comparison_runs
    path = filedialog.askopenfilename(
        title="Odaberi CSV sa simulacijom",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
    )
    if not path:
        return

    try:
        df = pd.read_csv(path)
    except Exception as e:
        messagebox.showerror("Greška", f"Ne mogu učitati CSV:\n{e}")
        return

    # izvući parametre za label
    try:
        params = df[["resource_regen", "move_prob_prey", "predation_success_prob"]].iloc[0]
        label = (
            f"{path.split('/')[-1]} "
            f"(r={params['resource_regen']}, "
            f"m={params['move_prob_prey']}, "
            f"p={params['predation_success_prob']})"
        )
    except Exception:
        label = path.split("/")[-1]

    comparison_runs.append((label, df))
    draw_comparison_plot()


def draw_comparison_plot():
    """Nacrtaj oscilacije populacija za sve učitane CSV-ove na istom grafu."""
    for child in frame_analysis4_canvas.winfo_children():
        child.destroy()

    if not comparison_runs:
        lbl = tk.Label(frame_analysis4_canvas, text="Još nema učitanih simulacija za usporedbu.")
        lbl.pack(pady=10)
        return

    fig = Figure(figsize=(7, 4))
    ax = fig.add_subplot(111)

    for label, df in comparison_runs:
        alive_prey = df[df["role"] == "prey"].groupby("day")["alive"].sum()
        ax.plot(alive_prey.index, alive_prey.values, label=f"Plijen: {label}")

    ax.set_xlabel("Dan")
    ax.set_ylabel("Broj plijenova")
    ax.set_title("Oscilacije populacije plijena za različite postavke parametara")
    ax.legend(fontsize=7)

    canvas = FigureCanvasTkAgg(fig, master=frame_analysis4_canvas)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)


# ---------- GUI: glavni prozor + tabovi ----------

root = tk.Tk()
root.title("Višeagentna simulacija ekosustava")

notebook = ttk.Notebook(root)
tab_sim = ttk.Frame(notebook)
tab_an1 = ttk.Frame(notebook)
tab_an2 = ttk.Frame(notebook)
tab_an3 = ttk.Frame(notebook)
tab_an4 = ttk.Frame(notebook)  
tab_data = ttk.Frame(notebook)

notebook.add(tab_sim, text="Simulacija")
notebook.add(tab_an1, text="Analiza 1")
notebook.add(tab_an2, text="Analiza 2")
notebook.add(tab_an3, text="Analiza 3")
notebook.add(tab_an4, text="Analiza 4")   
notebook.add(tab_data, text="Podaci")
notebook.pack(fill="both", expand=True)

# --- Tab Simulacija ---

frame_sim = ttk.LabelFrame(tab_sim, text="Parametri simulacije")
frame_sim.pack(padx=10, pady=10, fill="x")

tk.Label(frame_sim, text="Početni broj plijenova:").grid(row=0, column=0, sticky="w", pady=2)
entry_prey = tk.Entry(frame_sim, width=10)
entry_prey.insert(0, "5")
entry_prey.grid(row=0, column=1, padx=5)

tk.Label(frame_sim, text="Početni broj grabežljivaca:").grid(row=1, column=0, sticky="w", pady=2)
entry_pred = tk.Entry(frame_sim, width=10)
entry_pred.insert(0, "2")
entry_pred.grid(row=1, column=1, padx=5)

tk.Label(frame_sim, text="Broj dana simulacije:").grid(row=2, column=0, sticky="w", pady=2)
entry_days = tk.Entry(frame_sim, width=10)
entry_days.insert(0, "30")
entry_days.grid(row=2, column=1, padx=5)

tk.Label(frame_sim, text="Brzina regeneracije resursa:").grid(row=3, column=0, sticky="w", pady=2)
entry_regen = tk.Entry(frame_sim, width=10)
entry_regen.insert(0, "2")
entry_regen.grid(row=3, column=1, padx=5)

tk.Label(frame_sim, text="Vjerojatnost migracije plijena:").grid(row=4, column=0, sticky="w", pady=2)
entry_move_prob = tk.Entry(frame_sim, width=10)
entry_move_prob.insert(0, "0.5")
entry_move_prob.grid(row=4, column=1, padx=5)

tk.Label(frame_sim, text="Intenzitet predacije (p):").grid(row=5, column=0, sticky="w", pady=2)
entry_pred_prob = tk.Entry(frame_sim, width=10)
entry_pred_prob.insert(0, "0.7")
entry_pred_prob.grid(row=5, column=1, padx=5)

status_var = tk.StringVar(value="Spremno.")
lbl_status = tk.Label(tab_sim, textvariable=status_var, fg="blue")
lbl_status.pack(pady=5)

btn_start = tk.Button(tab_sim, text="Pokreni simulaciju", command=start_simulation)
btn_start.pack(pady=10)


# --- Tabovi Analiza i Podaci ---

frame_analysis1 = ttk.Frame(tab_an1)
frame_analysis1.pack(fill="both", expand=True, padx=10, pady=10)

frame_analysis2 = ttk.Frame(tab_an2)
frame_analysis2.pack(fill="both", expand=True, padx=10, pady=10)

frame_analysis3 = ttk.Frame(tab_an3)
frame_analysis3.pack(fill="both", expand=True, padx=10, pady=10)

# Analiza 4: gumb + frame za graf
btn_add_csv = tk.Button(
    tab_an4,
    text="Učitaj CSV i dodaj u usporedbu",
    command=add_csv_to_comparison,
)
btn_add_csv.pack(pady=5)

frame_analysis4_canvas = ttk.Frame(tab_an4)
frame_analysis4_canvas.pack(fill="both", expand=True, padx=10, pady=5)

frame_data = ttk.Frame(tab_data)
frame_data.pack(fill="both", expand=True, padx=10, pady=10)

root.mainloop()

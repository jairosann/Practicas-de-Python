# batalla_tactica.py
# Requiere: pip install colorama

import os
import random
import time
from dataclasses import dataclass, field
from typing import List, Tuple
from colorama import init, Fore, Back, Style

init(autoreset=True)

# ===== util =====

def bar(current: int, maxv: int, size: int = 24,
        color_full=Fore.GREEN, color_mid=Fore.YELLOW, color_low=Fore.RED) -> str:
    current = max(0, min(current, maxv))
    if maxv <= 0:
        frac_color = color_low
        filled = 0
    else:
        filled = int(size * current / maxv)
        frac = current / maxv
        frac_color = color_full if frac >= 0.6 else (color_mid if 0.3 <= frac < 0.6 else color_low)
    empty = size - filled
    return f"{frac_color}{'█'*filled}{Style.DIM}{'·'*empty}{Style.RESET_ALL}"

def energy_bar(e: int, maxe: int, size: int = 12) -> str:
    e = max(0, min(e, maxe))
    filled = 0 if maxe <= 0 else int(size * e / maxe)
    empty = size - filled
    return f"{Fore.CYAN}{'■'*filled}{Style.DIM}{'·'*empty}{Style.RESET_ALL}"

def clamp(a, lo, hi):
    return max(lo, min(a, hi))

def slow_print(s: str, delay: float = 0.01):
    for ch in s:
        print(ch, end="", flush=True)
        time.sleep(delay)
    print()

def clear():
    # Funciona en Windows y Unix
    os.system("cls" if os.name == "nt" else "clear")

# ===== core =====

@dataclass
class Fighter:
    nombre: str
    max_hp: int
    max_en: int
    atk: int
    df: int
    crit: float          # 0..1
    evd: float           # 0..1
    hp: int = field(init=False)
    en: int = field(init=False)
    cargas: int = field(default=2)  # recargas de energía
    estado: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.hp = self.max_hp
        self.en = self.max_en // 2

    def vivo(self) -> bool:
        return self.hp > 0

    def recibir(self, dmg: int):
        self.hp = clamp(self.hp - max(0, dmg), 0, self.max_hp)

    def recargar(self):
        if self.cargas <= 0:
            return False
        self.cargas -= 1
        gain = max(6, self.max_en // 2)
        self.en = clamp(self.en + gain, 0, self.max_en)
        return True

    def gastar(self, cost: int) -> bool:
        if self.en < cost:
            return False
        self.en -= cost
        return True

# ===== combate =====

def calc_daño(atacante: Fighter, defensor: Fighter, base: int, multiplicador: float = 1.0) -> Tuple[int, str]:
    # evasión
    if random.random() < defensor.evd:
        return 0, f"{Style.DIM}ESQUIVA{Style.RESET_ALL}"
    # crítico
    es_crit = random.random() < atacante.crit
    variacion = random.uniform(0.9, 1.1)
    bruto = int((base + atacante.atk - defensor.df) * multiplicador * variacion)
    bruto = max(0, bruto)
    if es_crit:
        bruto = int(bruto * 1.5)
    return bruto, (f"{Fore.YELLOW}CRÍTICO{Style.RESET_ALL}" if es_crit else "")

def pintar_panel(j: Fighter, e: Fighter, ronda: int):
    clear()
    titulo = f"{Back.WHITE}{Fore.BLACK}  BATALLA TÁCTICA  {Style.RESET_ALL}  {Style.DIM}Ronda {ronda}{Style.RESET_ALL}"
    print(titulo)
    print()
    # Jugador
    print(f"{Fore.CYAN}» {j.nombre}{Style.RESET_ALL}")
    print(f"  HP [{bar(j.hp, j.max_hp)}] {j.hp}/{j.max_hp}   EN [{energy_bar(j.en, j.max_en)}] {j.en}/{j.max_en}   Recargas: {j.cargas}")
    if j.estado:
        print(f"  Estados: {', '.join(j.estado)}")
    print()
    # Enemigo
    print(f"{Fore.MAGENTA}» {e.nombre}{Style.RESET_ALL}")
    print(f"  HP [{bar(e.hp, e.max_hp)}] {e.hp}/{e.max_hp}   EN [{energy_bar(e.en, e.max_en)}] {e.en}/{e.max_en}")
    if e.estado:
        print(f"  Estados: {', '.join(e.estado)}")
    print()
    print(Style.DIM + "Acciones: [A]tacar  [D]efender  [E]special  [R]ecargar  [Q]salir" + Style.RESET_ALL)

def aplicar_defensa(dmg: int, defensor: Fighter) -> int:
    return int(dmg * 0.6) if "DEF" in defensor.estado else dmg

def turno_jugador(j: Fighter, e: Fighter) -> bool:
    while True:
        elec = input(Fore.CYAN + "Tu elección: " + Style.RESET_ALL).strip().lower()
        if elec == 'q':
            return False
        if elec == 'a':
            base = 8
            dmg, tag = calc_daño(j, e, base)
            dmg = aplicar_defensa(dmg, e)
            e.recibir(dmg)
            slow_print(f"Atacas {Fore.GREEN}+{dmg}{Style.RESET_ALL} {tag}")
            return True
        if elec == 'd':
            if "DEF" not in j.estado:
                j.estado.append("DEF")
            slow_print(Fore.CYAN + "Adoptas guardia. Daño entrante reducido." + Style.RESET_ALL)
            return True
        if elec == 'e':
            cost = 8
            if not j.gastar(cost):
                print(Fore.RED + "Energía insuficiente." + Style.RESET_ALL)
                continue
            base = 12
            mult = 1.25
            dmg, tag = calc_daño(j, e, base, mult)
            dmg = aplicar_defensa(dmg, e)
            e.recibir(dmg)
            slow_print(f"Especial {Fore.GREEN}+{dmg}{Style.RESET_ALL} {tag}")
            return True
        if elec == 'r':
            if j.recargar():
                slow_print(Fore.CYAN + "Recargas energía." + Style.RESET_ALL)
                return True
            print(Fore.RED + "Sin recargas." + Style.RESET_ALL)
        else:
            print(Style.DIM + "Entrada inválida." + Style.RESET_ALL)

def turno_enemigo(e: Fighter, j: Fighter):
    time.sleep(0.4)
    # lógica simple
    if e.en < 6 and e.cargas > 0 and random.random() < 0.6:
        e.recargar()
        slow_print(Fore.MAGENTA + f"{e.nombre}" + Style.RESET_ALL + " recarga energía.")
        return
    mov = random.random()
    if mov < 0.55:
        base = 7
        dmg, tag = calc_daño(e, j, base)
        dmg = aplicar_defensa(dmg, j)
        j.recibir(dmg)
        slow_print(Fore.MAGENTA + f"{e.nombre}" + Style.RESET_ALL + f" ataca {Fore.RED}-{dmg}{Style.RESET_ALL} {tag}")
    elif mov < 0.75:
        if "DEF" not in e.estado:
            e.estado.append("DEF")
        slow_print(Fore.MAGENTA + f"{e.nombre}" + Style.RESET_ALL + " se defiende.")
    else:
        if e.gastar(6):
            base = 10
            dmg, tag = calc_daño(e, j, base, 1.15)
            dmg = aplicar_defensa(dmg, j)
            j.recibir(dmg)
            slow_print(Fore.MAGENTA + f"{e.nombre}" + Style.RESET_ALL + f" usa técnica {Fore.RED}-{dmg}{Style.RESET_ALL} {tag}")
        else:
            base = 7
            dmg, tag = calc_daño(e, j, base)
            dmg = aplicar_defensa(dmg, j)
            j.recibir(dmg)
            slow_print(Fore.MAGENTA + f"{e.nombre}" + Style.RESET_ALL + f" ataca {Fore.RED}-{dmg}{Style.RESET_ALL} {tag}")

def limpiar_estados(f: Fighter):
    # DEF dura 1 turno
    if "DEF" in f.estado:
        f.estado = [s for s in f.estado if s != "DEF"]

def intro():
    clear()
    print(f"{Back.WHITE}{Fore.BLACK}  BATALLA TÁCTICA  {Style.RESET_ALL}")
    print(Style.DIM + "Terminal • Colorama • Python 3.x" + Style.RESET_ALL)
    print()
    time.sleep(0.6)

def crear_combate():
    try:
        nombre = input("Tu nombre: ").strip()
    except EOFError:
        nombre = ""
    if not nombre:
        nombre = "Héroe"
    jugador = Fighter(
        nombre=nombre, max_hp=90, max_en=18, atk=9, df=4, crit=0.15, evd=0.08
    )
    enemigo = Fighter(
        nombre="Centinela", max_hp=100, max_en=16, atk=8, df=5, crit=0.10, evd=0.06
    )
    return jugador, enemigo

def fin(j: Fighter, e: Fighter):
    if j.vivo() and not e.vivo():
        slow_print(Fore.GREEN + "Victoria." + Style.RESET_ALL, 0.02)
    elif e.vivo() and not j.vivo():
        slow_print(Fore.RED + "Derrota." + Style.RESET_ALL, 0.02)
    else:
        slow_print("Empate.", 0.02)

def loop():
    intro()
    j, e = crear_combate()
    ronda = 1
    while j.vivo() and e.vivo():
        pintar_panel(j, e, ronda)
        ok = turno_jugador(j, e)
        if not ok:
            print(Style.DIM + "Salida." + Style.RESET_ALL)
            return
        if not e.vivo():
            break
        limpiar_estados(j)
        time.sleep(0.3)
        turno_enemigo(e, j)
        limpiar_estados(e)
        ronda += 1
        time.sleep(0.6)
    pintar_panel(j, e, ronda)
    fin(j, e)

if __name__ == "__main__":
    try:
        loop()
    except KeyboardInterrupt:
        print("\nInterrumpido.")


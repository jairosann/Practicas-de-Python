from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
import random

# Crear consola Rich
console = Console()

def mostrar_estado(jugador, vida, energia, recargas):
    """Muestra el estado del jugador con barras visuales mejoradas y colores vibrantes."""
    vida_barra = "[bold green]" + "█" * max(vida // 6, 0) + "[/bold green]" + "[bold red]" + "░" * max(20 - vida // 6, 0) + "[/bold red]"
    energia_barra = "[bold yellow]■[/bold yellow] " * energia + "[dim white]□[/dim white] " * (5 - energia)
    recargas_barra = "[bold red]■[/bold red]" if recargas > 0 else "[dim white]□[/dim white]"

    console.print(Panel.fit(
        f"[cyan bold]{jugador}[/cyan bold]\n"
        f"[green bold]VIDA:[/green bold] {vida}/125 {vida_barra}\n"
        f"[yellow bold]ENERGÍA:[/yellow bold] {energia_barra}\n"
        f"[red bold]RECARGAS:[/red bold] {recargas_barra}",
        title=f"[magenta bold]{' ESTADÍSTICAS ':-^30}[/magenta bold]",
        border_style="bright_magenta"
    ))

def atacar(jugador, energia, municiones):
    """Realiza un ataque y reduce la energía del jugador."""
    if energia <= 0:
        console.print(f"[red bold]{jugador} no tiene suficiente energía para atacar![/red bold]")
        return 0, energia

    if municiones not in [1, 2, 3]:
        console.print(f"[red bold]Cantidad de municiones inválida. Debe ser entre 1 y 3.[/red bold]")
        return 0, energia

    if energia < municiones:
        console.print(f"[red bold]{jugador} no tiene suficiente energía para usar {municiones} municiones![/red bold]")
        return 0, energia

    energia -= municiones
    if municiones == 1:
        dano = random.randint(1, 20)
    elif municiones == 2:
        dano = random.randint(1, 18) * 2
    elif municiones == 3:
        dano = random.randint(1, 15) * 3

    console.print(f"[yellow bold]{jugador} realizó un ataque con {dano} de daño![/yellow bold]")
    return dano, energia

def recargar_energia(jugador, energia):
    """Recarga energía del jugador."""
    if energia >= 5:
        console.print(f"[red bold]{jugador} ya tiene la energía máxima![/red bold]")
        return energia

    recarga = random.randint(1, 2)
    energia = min(energia + recarga, 5)
    console.print(f"[yellow bold]{jugador} recarga {recarga} de energía.[/yellow bold]")
    return energia

def recargar_vida(jugador, vida, recargas):
    """Recarga vida del jugador si tiene recargas disponibles."""
    if recargas <= 0:
        console.print(f"[red bold]{jugador} no tiene recargas de vida disponibles![/red bold]")
        return vida, recargas

    vida_extra = random.randint(1, 15)
    vida = min(vida + vida_extra, 125)
    recargas -= 1
    console.print(f"[green bold]{jugador} recupera {vida_extra} puntos de vida.[/green bold]")
    return vida, recargas

def obtener_recarga(jugador, recargas):
    """Otorga una recarga de vida al jugador si es exitoso."""
    if recargas >= 1:
        console.print(f"[red bold]{jugador} ya tiene una recarga disponible![/red bold]")
        return recargas

    exito = random.choice([True, False])
    if exito:
        recargas += 1
        console.print(f"[green bold]¡{jugador} ha obtenido una recarga de vida![/green bold]")
    else:
        console.print(f"[red bold]{jugador} no logró obtener una recarga de vida.[/red bold]")
    return recargas

def juego_batalla_tactica():
    """Juego principal de la batalla táctica."""
    console.print("[yellow bold on black]=== Batalla Táctica ===[/yellow bold on black]")
    jugador1 = Prompt.ask("[bold cyan]Nombre del Jugador 1[/bold cyan]")
    jugador2 = Prompt.ask("[bold cyan]Nombre del Jugador 2[/bold cyan]")

    vida1, energia1, recargas1 = 100, 3, 1
    vida2, energia2, recargas2 = 100, 3, 1

    while vida1 > 0 and vida2 > 0:
        mostrar_estado(jugador1, vida1, energia1, recargas1)
        mostrar_estado(jugador2, vida2, energia2, recargas2)

        # Turno del jugador 1
        console.print(f"[magenta bold]Turno de {jugador1}[/magenta bold]")
        console.print("1. Atacar\n2. Recargar Energía\n3. Recargar Vida\n4. Obtener Recarga de Vida")
        accion = Prompt.ask("Elige una acción", choices=["1", "2", "3", "4"])

        if accion == "1":
            try:
                municiones = int(Prompt.ask("¿Cuántas municiones deseas usar (1-3)?"))
                ataque, energia1 = atacar(jugador1, energia1, municiones)
                vida2 -= ataque
            except ValueError:
                console.print("[red bold]Entrada inválida. Debes ingresar un número válido.[/red bold]")
        elif accion == "2":
            energia1 = recargar_energia(jugador1, energia1)
        elif accion == "3":
            vida1, recargas1 = recargar_vida(jugador1, vida1, recargas1)
        elif accion == "4":
            recargas1 = obtener_recarga(jugador1, recargas1)

        if vida2 <= 0:
            console.print(f"[green bold]{jugador2} ha sido derrotado. ¡{jugador1} gana![/green bold]")
            break

        # Turno del jugador 2
        console.print(f"[magenta bold]Turno de {jugador2}[/magenta bold]")
        console.print("1. Atacar\n2. Recargar Energía\n3. Recargar Vida\n4. Obtener Recarga de Vida")
        accion = Prompt.ask("Elige una acción", choices=["1", "2", "3", "4"])

        if accion == "1":
            try:
                municiones = int(Prompt.ask("¿Cuántas municiones deseas usar (1-3)?"))
                ataque, energia2 = atacar(jugador2, energia2, municiones)
                vida1 -= ataque
            except ValueError:
                console.print("[red bold]Entrada inválida. Debes ingresar un número válido.[/red bold]")
        elif accion == "2":
            energia2 = recargar_energia(jugador2, energia2)
        elif accion == "3":
            vida2, recargas2 = recargar_vida(jugador2, vida2, recargas2)
        elif accion == "4":
            recargas2 = obtener_recarga(jugador2, recargas2)

        if vida1 <= 0:
            console.print(f"[green bold]{jugador1} ha sido derrotado. ¡{jugador2} gana![/green bold]")
            break

    console.print("[yellow bold on black]=== Fin del Juego ===[/yellow bold on black]")

if __name__ == "__main__":
    juego_batalla_tactica()
import pygame
import sys

# --- CONFIGURACIÓN BÁSICA ---
pygame.init()
WIDTH, HEIGHT = 800, 600
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pong")

FPS = 60
CLOCK = pygame.time.Clock()

# --- COLORES ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# --- PALA ---
PADDLE_WIDTH, PADDLE_HEIGHT = 15, 100
PADDLE_SPEED = 7
SCORE_LIMIT = 7
BASE_BALL_SPEED = 6
SPEED_INCREASE_FACTOR = 1.08  # factor multiplicador al rebotar en pala
MAX_BALL_SPEED = 12
AI_SPEED = 6  # velocidad máxima de la pala controlada por la IA

# Izquierda
left_paddle = pygame.Rect(50, HEIGHT // 2 - PADDLE_HEIGHT // 2,
                          PADDLE_WIDTH, PADDLE_HEIGHT)
# Derecha
right_paddle = pygame.Rect(WIDTH - 50 - PADDLE_WIDTH,
                           HEIGHT // 2 - PADDLE_HEIGHT // 2,
                           PADDLE_WIDTH, PADDLE_HEIGHT)

# --- PELOTA ---
BALL_SIZE = 20
ball = pygame.Rect(WIDTH // 2 - BALL_SIZE // 2,
                   HEIGHT // 2 - BALL_SIZE // 2,
                   BALL_SIZE, BALL_SIZE)
ball_speed_x = BASE_BALL_SPEED
ball_speed_y = BASE_BALL_SPEED

# --- MARCADOR ---
left_score = 0
right_score = 0
FONT = pygame.font.SysFont("Consolas", 40)


def reset_ball(direction: int):
    """Coloca la pelota en el centro y la lanza hacia la izquierda (-1) o derecha (+1)."""
    import random
    global ball_speed_x, ball_speed_y
    ball.center = (WIDTH // 2, HEIGHT // 2)
    # Reiniciar a velocidad base y darle una dirección vertical aleatoria
    ball_speed_x = BASE_BALL_SPEED * direction
    ball_speed_y = BASE_BALL_SPEED * (random.choice([-1, 1]))


def draw():
    """Dibuja todo en pantalla."""
    SCREEN.fill(BLACK)

    # Paddles y pelota
    pygame.draw.rect(SCREEN, WHITE, left_paddle)
    pygame.draw.rect(SCREEN, WHITE, right_paddle)
    pygame.draw.ellipse(SCREEN, WHITE, ball)

    # Línea central
    pygame.draw.aaline(SCREEN, WHITE, (WIDTH // 2, 0), (WIDTH // 2, HEIGHT))

    # Marcador
    score_text = FONT.render(f"{left_score}   {right_score}", True, WHITE)
    SCREEN.blit(score_text, (WIDTH // 2 - score_text.get_width() // 2, 20))

    # Mostrar límite y modo (si existe variable global)
    mode_text = "IA" if globals().get('ai_enabled', False) else "2 Jugadores"
    mode_surf = pygame.font.SysFont("Consolas", 20).render(f"Límite: {SCORE_LIMIT}  Modo: {mode_text}", True, WHITE)
    SCREEN.blit(mode_surf, (10, 10))

    pygame.display.flip()


def handle_input(ai_enabled: bool = False):
    """Mueve las palas según el teclado."""
    keys = pygame.key.get_pressed()

    # Pala izquierda: W / S
    if keys[pygame.K_w]:
        left_paddle.y -= PADDLE_SPEED
    if keys[pygame.K_s]:
        left_paddle.y += PADDLE_SPEED

    # Pala derecha: flechas arriba / abajo (solo si no hay IA)
    if not ai_enabled:
        if keys[pygame.K_UP]:
            right_paddle.y -= PADDLE_SPEED
        if keys[pygame.K_DOWN]:
            right_paddle.y += PADDLE_SPEED

    # Limitar a la pantalla
    left_paddle.y = max(0, min(HEIGHT - PADDLE_HEIGHT, left_paddle.y))
    right_paddle.y = max(0, min(HEIGHT - PADDLE_HEIGHT, right_paddle.y))


def update_ball():
    """Actualiza la posición de la pelota y gestiona rebotes y puntos."""
    global ball_speed_x, ball_speed_y, left_score, right_score

    # Movimiento básico
    ball.x += ball_speed_x
    ball.y += ball_speed_y

    # Rebote arriba/abajo
    if ball.top <= 0 or ball.bottom >= HEIGHT:
        ball_speed_y *= -1

    # Colisión con palas: invertir dirección X y aumentar velocidad progresivamente
    if ball.colliderect(left_paddle) and ball_speed_x < 0:
        ball_speed_x *= -1
        ball_speed_x = max(-MAX_BALL_SPEED, min(MAX_BALL_SPEED, ball_speed_x * SPEED_INCREASE_FACTOR))
        ball_speed_y = max(-MAX_BALL_SPEED, min(MAX_BALL_SPEED, ball_speed_y * SPEED_INCREASE_FACTOR))
    if ball.colliderect(right_paddle) and ball_speed_x > 0:
        ball_speed_x *= -1
        ball_speed_x = max(-MAX_BALL_SPEED, min(MAX_BALL_SPEED, ball_speed_x * SPEED_INCREASE_FACTOR))
        ball_speed_y = max(-MAX_BALL_SPEED, min(MAX_BALL_SPEED, ball_speed_y * SPEED_INCREASE_FACTOR))

    # Sale por la izquierda → punto para derecha
    if ball.right < 0:
        right_score += 1
        reset_ball(direction=1)

    # Sale por la derecha → punto para izquierda
    if ball.left > WIDTH:
        left_score += 1
        reset_ball(direction=-1)

    # Devolver si alguien llegó al límite
    if left_score >= SCORE_LIMIT or right_score >= SCORE_LIMIT:
        return True
    return False


def ai_move():
    """IA simple para controlar la pala derecha: sigue la pelota con limitación de velocidad."""
    diff = ball.centery - right_paddle.centery
    if abs(diff) < 5:
        return
    step = AI_SPEED if diff > 0 else -AI_SPEED
    if abs(diff) < abs(step):
        right_paddle.y += diff
    else:
        right_paddle.y += step
    right_paddle.y = max(0, min(HEIGHT - PADDLE_HEIGHT, right_paddle.y))


def start_menu():
    """Pantalla inicial para elegir modo de juego: 1 = 2 jugadores, 2 = vs IA."""
    global ai_enabled
    choosing = True
    ai_enabled = False
    small_font = pygame.font.SysFont("Consolas", 30)
    while choosing:
        CLOCK.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    ai_enabled = False
                    choosing = False
                if event.key == pygame.K_2:
                    ai_enabled = True
                    choosing = False
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

        SCREEN.fill(BLACK)
        title = FONT.render("PONG", True, WHITE)
        line1 = small_font.render("Presiona 1 para 2 Jugadores", True, WHITE)
        line2 = small_font.render("Presiona 2 para jugar contra la IA", True, WHITE)
        SCREEN.blit(title, (WIDTH // 2 - title.get_width() // 2, 100))
        SCREEN.blit(line1, (WIDTH // 2 - line1.get_width() // 2, 250))
        SCREEN.blit(line2, (WIDTH // 2 - line2.get_width() // 2, 300))
        pygame.display.flip()


def display_winner(winner_text: str):
    """Muestra la pantalla de victoria brevemente."""
    end_font = pygame.font.SysFont("Consolas", 50)
    start_time = pygame.time.get_ticks()
    while pygame.time.get_ticks() - start_time < 3000:  # 3 segundos
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        SCREEN.fill(BLACK)
        msg = end_font.render(winner_text, True, WHITE)
        SCREEN.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - msg.get_height() // 2))
        pygame.display.flip()


def main():
    global left_score, right_score

    # Mostrar menú de inicio para elegir modo
    start_menu()

    running = True
    while running:
        CLOCK.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            # Salir con ESC
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # Manejar entrada (si hay IA, la pala derecha no responde al jugador)
        handle_input(ai_enabled=ai_enabled)

        # Si hay IA, mover la pala derecha
        if ai_enabled:
            ai_move()

        # Actualizar pelota; update_ball devuelve True si alguien llegó al límite
        finished = update_ball()

        draw()

        if finished:
            # Mostrar quién ganó
            if left_score >= SCORE_LIMIT:
                winner = "Jugador Izquierdo gana!"
            else:
                winner = "Jugador Derecho gana!" if not ai_enabled else "IA gana!"
            display_winner(winner)
            running = False

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
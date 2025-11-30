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
ball_speed_x = 6
ball_speed_y = 6

# --- MARCADOR ---
left_score = 0
right_score = 0
FONT = pygame.font.SysFont("Consolas", 40)


def reset_ball(direction: int):
    """Coloca la pelota en el centro y la lanza hacia la izquierda (-1) o derecha (+1)."""
    global ball_speed_x, ball_speed_y
    ball.center = (WIDTH // 2, HEIGHT // 2)
    ball_speed_x = 6 * direction
    ball_speed_y = 6


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

    pygame.display.flip()


def handle_input():
    """Mueve las palas según el teclado."""
    keys = pygame.key.get_pressed()

    # Pala izquierda: W / S
    if keys[pygame.K_w]:
        left_paddle.y -= PADDLE_SPEED
    if keys[pygame.K_s]:
        left_paddle.y += PADDLE_SPEED

    # Pala derecha: flechas arriba / abajo
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

    # Colisión con palas
    if ball.colliderect(left_paddle) and ball_speed_x < 0:
        ball_speed_x *= -1
    if ball.colliderect(right_paddle) and ball_speed_x > 0:
        ball_speed_x *= -1

    # Sale por la izquierda → punto para derecha
    if ball.right < 0:
        right_score += 1
        reset_ball(direction=1)

    # Sale por la derecha → punto para izquierda
    if ball.left > WIDTH:
        left_score += 1
        reset_ball(direction=-1)


def main():
    global left_score, right_score

    running = True
    while running:
        CLOCK.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            # Salir con ESC
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        handle_input()
        update_ball()
        draw()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()

